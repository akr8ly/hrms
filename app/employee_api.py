import json
from datetime import datetime, timezone

from cryptography.exceptions import InvalidTag
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.encryption import get_employee_key_ring
from app.models import Department, Designation, Division, Employee, Location, OfficeAddress
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeRead,
    EmployeeUpdate,
    EmployeeQueryRead,
)
from app.dependencies import get_current_user, require_roles
from app.models.role import Role
from app.models.user import User

router = APIRouter(prefix="/employees", tags=["Employees"])
PII_FIELDS = ("first_name", "last_name", "date_of_birth", "personal_email",
              "work_email", "phone_number", "residential_address")


def lock_employee_writes(db):
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(72411920)"))


def find_employee(db, employee_id):
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(404, "Employee not found")
    return employee


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Duplicate employee code or conflicting database relationship") from None


def plaintext(employee, ring):
    values = {column.name: getattr(employee, column.name) for column in Employee.__table__.columns if column.name != "deleted_at"}
    try:
        for field in PII_FIELDS:
            values[field] = ring.decrypt(json.loads(values[field]))
    except (KeyError, ValueError, TypeError, InvalidTag):
        raise HTTPException(503, "Employee data could not be decrypted with the configured keys") from None
    return values


def read_response(employee, ring):
    return EmployeeRead.model_validate(plaintext(employee, ring))

def get_user_role(db: Session, user: User) -> str:
    role = db.get(Role, user.role_id)

    if role is None or role.name not in (
        "admin",
        "employee",
        "query",
    ):
        raise HTTPException(
            403,
            "Your account does not have a valid role",
        )

    return role.name


def validate_references(db, data, employee_id=None):
    for field, model in (("division_id", Division), ("department_id", Department),
                         ("designation_id", Designation), ("location_id", Location),
                         ("office_address_id", OfficeAddress)):
        if db.get(model, data[field]) is None:
            raise HTTPException(422, f"{field} must reference an existing record")
    if db.get(OfficeAddress, data["office_address_id"]).location_id != data["location_id"]:
        raise HTTPException(422, "Office address does not belong to the selected location")

    manager_id = data.get("reporting_manager_id")
    visited = {employee_id} if employee_id is not None else set()
    while manager_id is not None:
        if manager_id in visited:
            raise HTTPException(422, "Reporting manager would create a reporting cycle")
        visited.add(manager_id)
        manager = db.get(Employee, manager_id)
        if manager is None:
            raise HTTPException(422, "Reporting manager does not exist")
        manager_id = manager.reporting_manager_id


def storage_values(payload, ring):
    values = payload.model_dump()
    encoded = payload.model_dump(mode="json")
    for field in PII_FIELDS:
        values[field] = json.dumps(ring.encrypt(encoded[field]))
    return values


@router.post(
    "",
    response_model=EmployeeRead,
    status_code=201,
    dependencies=[Depends(require_roles("admin"))],
)

def create_employee(data: EmployeeCreate, db: Session = Depends(get_db), ring=Depends(get_employee_key_ring)):
    lock_employee_writes(db)
    validate_references(db, data.model_dump())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    employee = Employee(**storage_values(data, ring), created_at=now, updated_at=now)
    db.add(employee)
    commit(db)
    db.refresh(employee)
    return read_response(employee, ring)


@router.get(
    "",
    response_model=list[EmployeeRead | EmployeeQueryRead],
)
def get_employees(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(get_current_user),
):
    role = get_user_role(db, current_user)
    statement = select(Employee)

    if role == "employee":
        if current_user.employee_id is None:
            return []

        statement = statement.where(
            Employee.id == current_user.employee_id
        )

    employees = db.scalars(
        statement.order_by(Employee.id)
        .offset(offset)
        .limit(limit)
    ).all()

    if role == "query":
        return [
            EmployeeQueryRead.model_validate(employee)
            for employee in employees
        ]

    return [
        read_response(employee, ring)
        for employee in employees
    ]

@router.get(
    "/{employee_id}",
    response_model=EmployeeRead | EmployeeQueryRead,
)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(get_current_user),
):
    role = get_user_role(db, current_user)

    if role == "employee":
        if current_user.employee_id != employee_id:
            raise HTTPException(403, "You can only view your own profile")

    employee = find_employee(db, employee_id)

    if role == "query":
        return EmployeeQueryRead.model_validate(employee)

    return read_response(employee, ring)




@router.patch("/{employee_id}", response_model=EmployeeRead)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(get_current_user),
):
    role = get_user_role(db, current_user)

    if role == "query":
        raise HTTPException(403, "Your role has read-only access")

    if role == "employee":
        if current_user.employee_id != employee_id:
            raise HTTPException(403, "You can only update your own profile")

        allowed_fields = {
            "personal_email",
            "phone_number",
            "residential_address",
        }
        if not data.model_fields_set.issubset(allowed_fields):
            raise HTTPException(403, "You can only update your personal contact details")

    lock_employee_writes(db)
    employee = find_employee(db, employee_id)
    old = plaintext(employee, ring)
    merged = {name: old[name] for name in EmployeeCreate.model_fields}
    changes = data.model_dump(exclude_unset=True)
    merged.update(changes)
    try:
        validated = EmployeeCreate.model_validate(merged)
    except ValidationError:
        raise HTTPException(422, "Employee update contains invalid fields, null values or date ordering") from None
    validate_references(db, validated.model_dump(), employee_id)
    values = storage_values(validated, ring)
    for field in changes:
        setattr(employee, field, values[field])
    employee.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    commit(db)
    db.refresh(employee)
    return read_response(employee, ring)


@router.delete(
    "/{employee_id}",
    status_code=204,
    dependencies=[Depends(require_roles("admin"))],
)

def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    lock_employee_writes(db)
    employee = find_employee(db, employee_id)
    if db.scalar(select(Employee.id).where(Employee.reporting_manager_id == employee_id).limit(1)):
        raise HTTPException(409, "Reassign direct reports before deleting this employee")
    employee.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    employee.updated_at = employee.deleted_at
    commit(db)
    return Response(status_code=204)
