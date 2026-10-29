from datetime import datetime, timezone

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
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
    ChangePasswordRequest,
    ResetPasswordRequest,
    SecurityQuestionResponse,
    UserRegister,
    UserRead,
    UserLogin,
    TokenResponse,
    CurrentUserRead,
)
from app.login_protection import LoginAttemptLimiter
from app.security import (
    auth_settings,
    hash_password,
    normalize_security_answer,
    verify_password,
    create_access_token,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])
audit_logger = logging.getLogger("hrms.security.audit")
login_limiter = LoginAttemptLimiter(
    max_attempts=auth_settings.login_max_attempts,
    window_seconds=auth_settings.login_window_seconds,
    lockout_seconds=auth_settings.login_lockout_seconds,
)


def login_limit_keys(request: Request, username: str) -> tuple[str, str]:
    client_ip = request.client.host if request.client else "unknown"
    normalized_username = username.casefold().strip()
    return f"ip:{client_ip}", f"account:{normalized_username}"


def reject_failed_login(request: Request, username: str) -> None:
    keys = login_limit_keys(request, username)
    retry_after = login_limiter.record_failure(*keys)
    audit_logger.warning("event=login_failed username=%s ip=%s", username, request.client.host if request.client else "unknown")
    if retry_after:
        audit_logger.warning("event=login_locked username=%s ip=%s retry_after=%s", username, request.client.host if request.client else "unknown", retry_after)
        raise HTTPException(
            429,
            "Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )



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
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    keys = login_limit_keys(request, data.username)
    retry_after = login_limiter.blocked(*keys)
    if retry_after:
        raise HTTPException(
            429,
            "Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = db.scalar(
        select(User).where(User.username == data.username)
    )

    if user is None:
        reject_failed_login(request, data.username)
        raise HTTPException(401, "Invalid username or password")

    if not verify_password(
        data.password.get_secret_value(),
        user.password_hash,
    ):
        reject_failed_login(request, data.username)
        raise HTTPException(401, "Invalid username or password")

    login_limiter.record_success(*keys)
    audit_logger.info("event=login_succeeded username=%s ip=%s", data.username, request.client.host if request.client else "unknown")

    if user.approval_status == "pending":
        raise HTTPException(403, "Your registration is awaiting administrator approval")
    if user.approval_status == "rejected":
        raise HTTPException(403, "Your registration was rejected by an administrator")

    access_token = create_access_token(user.id)
    response.set_cookie(
        key="hrms_access_token",
        value=access_token,
        httponly=True,
        secure=auth_settings.cookie_secure,
        samesite="lax",
        max_age=30 * 60,
        path="/",
    )
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(
        key="hrms_access_token",
        secure=auth_settings.cookie_secure,
        samesite="lax",
        path="/",
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


@router.post("/change-password", status_code=204)
def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_password = data.current_password.get_secret_value()
    new_password = data.new_password.get_secret_value()
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if verify_password(new_password, current_user.password_hash):
        raise HTTPException(400, "New password must be different from the current password")
    current_user.password_hash = hash_password(new_password)
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
        approval_status=current_user.approval_status,
        role=role.name,
    )
