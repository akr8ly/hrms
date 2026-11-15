"""Read-only organisational structure derived from approved HR master data."""

from __future__ import annotations

from collections import defaultdict

from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.audit import record_audit_event
from app.employee_api import (
    EmployeeCreate,
    EmployeeRead,
    EmployeeUpdate,
    commit,
    lock_employee_writes,
    plaintext,
    read_response,
    storage_values,
    validate_references,
)
from app.encryption import get_employee_key_ring
from app.models import Department, Designation, Division, Employee
from app.models.user import User


router = APIRouter(prefix="/organization", tags=["Organisation"])


class OrganisationEmployeeRead(BaseModel):
    id: int
    employee_code: str
    name: str
    designation: str
    external_reports_to: str | None = None
    direct_reports: list["OrganisationEmployeeRead"] = Field(default_factory=list)


class OrganisationDepartmentRead(BaseModel):
    id: int
    code: str
    name: str
    employee_count: int
    employees: list[OrganisationEmployeeRead] = Field(default_factory=list)


class OrganisationDivisionRead(BaseModel):
    id: int
    code: str
    name: str
    employee_count: int
    departments: list[OrganisationDepartmentRead] = Field(default_factory=list)


class OrganisationTreeRead(BaseModel):
    name: str
    divisions: list[OrganisationDivisionRead] = Field(default_factory=list)


class OrganisationReportingLineRead(BaseModel):
    """The minimal employee data needed to administer a reporting line."""

    id: int
    employee_code: str
    name: str
    designation: str
    division: str
    department: str
    reporting_manager_id: int | None


class OrganisationReportingLineUpdate(BaseModel):
    """Set or clear the direct manager of an employee."""

    reporting_manager_id: int | None = Field(default=None, gt=0)


class TeamMemberCreate(BaseModel):
    """Data a reporting manager may provide for a new direct report.

    Organisational placement and employment status are derived server-side from
    the manager; they are deliberately not accepted from the browser.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    employee_code: str
    first_name: str
    last_name: str
    date_of_birth: date
    personal_email: str
    work_email: str
    phone_number: str
    residential_address: str
    employee_photo: str | None = None
    date_of_joining: date
    employment_type: str
    designation_id: int


class TeamDesignationRead(BaseModel):
    id: int
    code: str
    name: str


TEAM_UPDATE_FIELDS = {
    "first_name",
    "last_name",
    "date_of_birth",
    "personal_email",
    "work_email",
    "phone_number",
    "residential_address",
    "employee_photo",
    "date_of_joining",
    "employment_type",
}


def _active_employee_or_403(db: Session, user: User) -> Employee:
    """Return the employee record linked to an authenticated team manager."""
    if user.employee_id is None:
        raise HTTPException(403, "Your account is not linked to an employee record")
    manager = db.get(Employee, user.employee_id)
    if manager is None or manager.deleted_at is not None or manager.employment_status == "exited":
        raise HTTPException(403, "Your linked employee record is not active")
    return manager


def _reporting_manager_or_403(db: Session, user: User) -> Employee:
    """Return an active employee only when they currently manage a direct report."""
    manager = _active_employee_or_403(db, user)
    manages_direct_report = db.scalar(
        select(Employee.id)
        .where(Employee.reporting_manager_id == manager.id)
        .where(Employee.deleted_at.is_(None))
        .where(Employee.employment_status != "exited")
        .limit(1)
    )
    if manages_direct_report is None:
        raise HTTPException(403, "Only reporting managers can manage direct reports")
    return manager


def _direct_report_or_404(db: Session, manager_id: int, employee_id: int) -> Employee:
    """Avoid exposing whether an employee outside the manager's team exists."""
    employee = db.get(Employee, employee_id)
    if (
        employee is None
        or employee.deleted_at is not None
        or employee.employment_status == "exited"
        or employee.reporting_manager_id != manager_id
    ):
        raise HTTPException(404, "Direct report not found")
    return employee


def _employee_forest(employees: list[dict[str, object]]) -> list[dict[str, object]]:
    """Nest direct reports while keeping cross-department reports at their own node."""
    nodes = {
        int(employee["id"]): {
            "id": int(employee["id"]),
            "employee_code": str(employee["employee_code"]),
            "name": str(employee["name"]),
            "designation": str(employee["designation"]),
            "external_reports_to": employee.get("external_reports_to"),
            "direct_reports": [],
        }
        for employee in employees
    }
    roots: list[dict[str, object]] = []
    for employee in employees:
        employee_id = int(employee["id"])
        manager_id = employee.get("reporting_manager_id")
        if isinstance(manager_id, int) and manager_id in nodes:
            nodes[manager_id]["direct_reports"].append(nodes[employee_id])
        else:
            roots.append(nodes[employee_id])

    def sort_branch(node: dict[str, object]) -> None:
        reports = node["direct_reports"]
        assert isinstance(reports, list)
        reports.sort(key=lambda report: (str(report["name"]).casefold(), int(report["id"])))
        for report in reports:
            sort_branch(report)

    roots.sort(key=lambda node: (str(node["name"]).casefold(), int(node["id"])))
    for root in roots:
        sort_branch(root)
    return roots


def build_organisation_tree(
    *,
    employees: list[dict[str, object]],
    divisions: list[dict[str, object]],
    departments: list[dict[str, object]],
    designations: list[dict[str, object]],
) -> dict[str, object]:
    """Create the company → division → department → employee presentation tree."""
    division_by_id = {int(item["id"]): item for item in divisions}
    department_by_id = {int(item["id"]): item for item in departments}
    designation_by_id = {int(item["id"]): item for item in designations}
    employee_by_id = {int(item["id"]): item for item in employees}
    grouped: dict[tuple[int, int], list[dict[str, object]]] = defaultdict(list)

    for employee in employees:
        division_id = int(employee["division_id"])
        department_id = int(employee["department_id"])
        designation = designation_by_id.get(int(employee["designation_id"]), {})
        manager = employee_by_id.get(int(employee["reporting_manager_id"])) if employee.get("reporting_manager_id") is not None else None
        reports_to = None
        if manager is not None and (
            manager.get("division_id") != employee.get("division_id")
            or manager.get("department_id") != employee.get("department_id")
        ):
            manager_department = department_by_id.get(int(manager["department_id"]), {})
            reports_to = f"{manager['first_name']} {manager['last_name']} · {manager_department.get('name', 'another department')}"
        grouped[(division_id, department_id)].append(
            {
                "id": int(employee["id"]),
                "employee_code": employee["employee_code"],
                "name": f"{employee['first_name']} {employee['last_name']}".strip(),
                "designation": designation.get("name", "Unassigned designation"),
                "reporting_manager_id": employee.get("reporting_manager_id"),
                "external_reports_to": reports_to,
            }
        )

    division_rows: list[dict[str, object]] = []
    for division in sorted(divisions, key=lambda item: (str(item["name"]).casefold(), int(item["id"]))):
        division_id = int(division["id"])
        department_rows: list[dict[str, object]] = []
        for (group_division_id, department_id), members in grouped.items():
            if group_division_id != division_id:
                continue
            department = department_by_id.get(department_id)
            if department is None:
                continue
            department_rows.append(
                {
                    "id": department_id,
                    "code": str(department["code"]),
                    "name": str(department["name"]),
                    "employee_count": len(members),
                    "employees": _employee_forest(members),
                }
            )
        department_rows.sort(key=lambda item: (str(item["name"]).casefold(), int(item["id"])))
        division_rows.append(
            {
                "id": division_id,
                "code": str(division["code"]),
                "name": str(division["name"]),
                "employee_count": sum(int(item["employee_count"]) for item in department_rows),
                "departments": department_rows,
            }
        )
    return {"name": "Company", "divisions": division_rows}


def validate_reporting_line(
    *,
    employee_id: int,
    manager_id: int | None,
    manager_by_employee_id: dict[int, int | None],
) -> None:
    """Reject a self-reference or any manager chain that loops back to the employee."""
    if manager_id is None:
        return
    if manager_id == employee_id:
        raise ValueError("An employee cannot be their own reporting manager")

    visited = {employee_id}
    current_id = manager_id
    while current_id is not None:
        if current_id in visited:
            raise ValueError("Reporting manager would create a reporting cycle")
        visited.add(current_id)
        current_id = manager_by_employee_id.get(current_id)


@router.get("/team", response_model=list[EmployeeRead])
def get_my_team(
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(require_roles("employee")),
):
    """Return only the active employees who directly report to this manager."""
    manager = _reporting_manager_or_403(db, current_user)
    team = db.scalars(
        select(Employee)
        .where(Employee.reporting_manager_id == manager.id)
        .where(Employee.deleted_at.is_(None))
        .where(Employee.employment_status != "exited")
        .order_by(Employee.id)
    ).all()
    return [read_response(employee, ring) for employee in team]


@router.get("/team/designations", response_model=list[TeamDesignationRead])
def get_team_designations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("employee")),
):
    """Expose existing designation choices without granting master-data access."""
    _reporting_manager_or_403(db, current_user)
    return db.scalars(
        select(Designation)
        .where(Designation.deleted_at.is_(None))
        .order_by(Designation.name, Designation.id)
    ).all()


@router.post("/team", response_model=EmployeeRead, status_code=201)
def create_my_team_member(
    data: TeamMemberCreate,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(require_roles("employee")),
):
    """Create a direct report with placement inherited from the team manager."""
    manager = _reporting_manager_or_403(db, current_user)
    payload = data.model_dump()
    payload.update(
        {
            "employment_status": "active",
            "division_id": manager.division_id,
            "department_id": manager.department_id,
            "location_id": manager.location_id,
            "office_address_id": manager.office_address_id,
            "reporting_manager_id": manager.id,
        }
    )
    try:
        validated = EmployeeCreate.model_validate(payload)
    except ValidationError:
        raise HTTPException(422, "Team member contains invalid or incomplete fields") from None

    lock_employee_writes(db)
    validate_references(db, validated.model_dump())
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    employee = Employee(**storage_values(validated, ring), created_at=now, updated_at=now)
    db.add(employee)
    commit(db)
    db.refresh(employee)
    record_audit_event(
        db,
        event_type="organization.team_member.created",
        actor_user_id=current_user.id,
        details={"employee_id": employee.id, "manager_employee_id": manager.id},
    )
    db.commit()
    return read_response(employee, ring)


@router.patch("/team/{employee_id}", response_model=EmployeeRead)
def update_my_team_member(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(require_roles("employee")),
):
    """Update permitted employee data for one current direct report."""
    manager = _reporting_manager_or_403(db, current_user)
    changes = data.model_dump(exclude_unset=True)
    forbidden_fields = set(changes) - TEAM_UPDATE_FIELDS
    if forbidden_fields:
        raise HTTPException(403, "Managers cannot change organisational placement, status, or reporting lines")

    lock_employee_writes(db)
    employee = _direct_report_or_404(db, manager.id, employee_id)
    old = plaintext(employee, ring)
    merged = {name: old[name] for name in EmployeeCreate.model_fields}
    merged.update(changes)
    try:
        validated = EmployeeCreate.model_validate(merged)
    except ValidationError:
        raise HTTPException(422, "Team member update contains invalid fields or date ordering") from None
    values = storage_values(validated, ring)
    for field in changes:
        setattr(employee, field, values[field])
    employee.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    commit(db)
    db.refresh(employee)
    record_audit_event(
        db,
        event_type="organization.team_member.updated",
        actor_user_id=current_user.id,
        details={"employee_id": employee.id, "manager_employee_id": manager.id, "changed_fields": sorted(changes)},
    )
    db.commit()
    return read_response(employee, ring)


@router.delete("/team/{employee_id}", status_code=204)
def delete_my_team_member(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("employee")),
):
    """Soft-delete a direct report only when their own reporting branch is empty."""
    manager = _reporting_manager_or_403(db, current_user)
    lock_employee_writes(db)
    employee = _direct_report_or_404(db, manager.id, employee_id)
    if db.scalar(select(Employee.id).where(Employee.reporting_manager_id == employee.id).limit(1)):
        raise HTTPException(409, "Reassign this employee's direct reports before deleting them")
    employee.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    employee.updated_at = employee.deleted_at
    commit(db)
    record_audit_event(
        db,
        event_type="organization.team_member.deleted",
        actor_user_id=current_user.id,
        details={"employee_id": employee.id, "manager_employee_id": manager.id},
    )
    db.commit()


@router.get("/tree", response_model=OrganisationTreeRead)
def get_organisation_tree(
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    _current_user: User = Depends(require_roles("admin", "employee")),
):
    employees = db.scalars(
        select(Employee)
        .where(Employee.employment_status != "exited")
        .where(Employee.deleted_at.is_(None))
        .order_by(Employee.id)
    ).all()
    employee_rows = [plaintext(employee, ring) for employee in employees]
    master_data = lambda model: [
        {column.name: getattr(item, column.name) for column in model.__table__.columns if column.name != "deleted_at"}
        for item in db.scalars(select(model).where(model.deleted_at.is_(None))).all()
    ]
    return build_organisation_tree(
        employees=employee_rows,
        divisions=master_data(Division),
        departments=master_data(Department),
        designations=master_data(Designation),
    )


@router.get("/reporting-lines", response_model=list[OrganisationReportingLineRead])
def get_reporting_lines(
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    _current_user: User = Depends(require_roles("admin")),
):
    """Return only the data an administrator needs to maintain reporting lines."""
    employees = db.scalars(
        select(Employee)
        .where(Employee.employment_status != "exited")
        .where(Employee.deleted_at.is_(None))
        .order_by(Employee.id)
    ).all()
    divisions = {item.id: item.name for item in db.scalars(select(Division).where(Division.deleted_at.is_(None))).all()}
    departments = {item.id: item.name for item in db.scalars(select(Department).where(Department.deleted_at.is_(None))).all()}
    designations = {item.id: item.name for item in db.scalars(select(Designation).where(Designation.deleted_at.is_(None))).all()}

    reporting_lines = []
    for employee in employees:
        values = plaintext(employee, ring)
        reporting_lines.append(
            {
                "id": employee.id,
                "employee_code": employee.employee_code,
                "name": f"{values['first_name']} {values['last_name']}".strip(),
                "designation": designations.get(employee.designation_id, "Unassigned designation"),
                "division": divisions.get(employee.division_id, "Unassigned division"),
                "department": departments.get(employee.department_id, "Unassigned department"),
                "reporting_manager_id": employee.reporting_manager_id,
            }
        )
    return reporting_lines


@router.patch("/reporting-lines/{employee_id}", response_model=OrganisationReportingLineRead)
def update_reporting_line(
    employee_id: int,
    data: OrganisationReportingLineUpdate,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
    current_user: User = Depends(require_roles("admin")),
):
    """Change one direct reporting line without accepting a full employee profile."""
    lock_employee_writes(db)
    employee = db.get(Employee, employee_id)
    if employee is None or employee.deleted_at is not None or employee.employment_status == "exited":
        raise HTTPException(404, "Active employee not found")

    manager_id = data.reporting_manager_id
    active_employees = db.scalars(
        select(Employee)
        .where(Employee.employment_status != "exited")
        .where(Employee.deleted_at.is_(None))
    ).all()
    manager_by_employee_id = {item.id: item.reporting_manager_id for item in active_employees}
    if manager_id is not None and manager_id not in manager_by_employee_id:
        raise HTTPException(422, "Reporting manager must reference an active employee")
    manager = next((item for item in active_employees if item.id == manager_id), None)
    try:
        validate_reporting_line(
            employee_id=employee_id,
            manager_id=manager_id,
            manager_by_employee_id=manager_by_employee_id,
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from None

    employee.reporting_manager_id = manager_id
    employee.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    record_audit_event(
        db,
        event_type="organization.reporting_line.updated",
        actor_user_id=current_user.id,
        details={"employee_id": employee_id, "reporting_manager_id": manager_id},
    )
    db.commit()

    values = plaintext(employee, ring)
    designation = db.get(Designation, employee.designation_id)
    division = db.get(Division, employee.division_id)
    department = db.get(Department, employee.department_id)
    return {
        "id": employee.id,
        "employee_code": employee.employee_code,
        "name": f"{values['first_name']} {values['last_name']}".strip(),
        "designation": designation.name if designation is not None else "Unassigned designation",
        "division": division.name if division is not None else "Unassigned division",
        "department": department.name if department is not None else "Unassigned department",
        "reporting_manager_id": manager.id if manager is not None else None,
    }

