from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.role import Role
from app.models.user import User
from app.models import Department, Designation, Division, Employee, Location, OfficeAddress
from app.dependencies import get_current_user
from app.encryption import get_employee_key_ring
from app.employee_api import lock_employee_writes, storage_values, validate_references
from app.schemas.user import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    SecurityQuestionResponse,
    UserRegister,
    UserRead,
    UserLogin,
    TokenResponse,
    CurrentUserRead,
)
from app.security import (
    hash_password,
    normalize_security_answer,
    verify_password,
    create_access_token,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])


def master_rows(rows):
    return [
        {
            column.name: getattr(row, column.name)
            for column in row.__table__.columns
            if column.name != "deleted_at"
        }
        for row in rows
    ]


@router.get("/registration-options")
def registration_options(db: Session = Depends(get_db)):
    return {
        "divisions": master_rows(db.scalars(select(Division).order_by(Division.name)).all()),
        "departments": master_rows(db.scalars(select(Department).order_by(Department.name)).all()),
        "designations": master_rows(db.scalars(select(Designation).order_by(Designation.name)).all()),
        "locations": master_rows(db.scalars(select(Location).order_by(Location.name)).all()),
        "office_addresses": master_rows(
            db.scalars(select(OfficeAddress).order_by(OfficeAddress.city)).all()
        ),
    }

@router.post("/register", response_model=UserRead, status_code=201)
def register(
    data: UserRegister,
    db: Session = Depends(get_db),
    ring=Depends(get_employee_key_ring),
):
    role = db.scalar(
        select(Role).where(Role.name == data.role)
    )

    if role is None:
        raise HTTPException(503, f"{data.role.title()} role is not configured")

    employee = None
    if data.employee is not None:
        lock_employee_writes(db)
        validate_references(db, data.employee.model_dump())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        employee = Employee(
            **storage_values(data.employee, ring),
            created_at=now,
            updated_at=now,
        )
        db.add(employee)

        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Employee code or email is already registered") from None

    user = User(
        username=data.username,
        password_hash=hash_password(data.password.get_secret_value()),
        security_question=data.security_question,
        security_answer_hash=hash_password(
            normalize_security_answer(data.security_answer.get_secret_value())
        ),
        approval_status="pending",
        role_id=role.id,
        employee_id=employee.id if employee is not None else None,
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Username or employee code is unavailable"
        ) from None

    db.refresh(user)
    return user

@router.post("/login", response_model=TokenResponse)
def login(
    data: UserLogin,
    db: Session = Depends(get_db),
):
    user = db.scalar(
        select(User).where(User.username == data.username)
    )

    if user is None:
        raise HTTPException(401, "Invalid username or password")

    if not verify_password(
        data.password.get_secret_value(),
        user.password_hash,
    ):
        raise HTTPException(401, "Invalid username or password")

    if user.approval_status == "pending":
        raise HTTPException(403, "Your registration is awaiting administrator approval")
    if user.approval_status == "rejected":
        raise HTTPException(403, "Your registration was rejected by an administrator")

    return TokenResponse(
        access_token=create_access_token(user.id)
    )


@router.post("/forgot-password", response_model=SecurityQuestionResponse)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if user is None or user.security_question is None or user.security_answer_hash is None:
        raise HTTPException(404, "Password recovery is not available for this account")
    return SecurityQuestionResponse(security_question=user.security_question)


@router.post("/reset-password", status_code=204)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if user is None or user.security_answer_hash is None:
        raise HTTPException(400, "Username or security answer is incorrect")
    answer = normalize_security_answer(data.security_answer.get_secret_value())
    if not verify_password(answer, user.security_answer_hash):
        raise HTTPException(400, "Username or security answer is incorrect")
    user.password_hash = hash_password(data.new_password.get_secret_value())
    db.commit()
    return None

@router.get("/me", response_model=CurrentUserRead)
def get_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = db.get(Role, current_user.role_id)

    if role is None:
        raise HTTPException(500, "User role is not configured")

    return CurrentUserRead(
        id=current_user.id,
        username=current_user.username,
        role_id=current_user.role_id,
        employee_id=current_user.employee_id,
        role=role.name,
    )
