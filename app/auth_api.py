from datetime import datetime, timezone
from hashlib import sha256
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.auth_state import token_state
from app.database import get_db
from app.models.role import Role
from app.models.user import User
from app.models import Department, Designation, Division, Employee, Location, OfficeAddress
from app.dependencies import get_current_user
from app.encryption import get_employee_key_ring
from app.employee_api import lock_employee_writes, storage_values, validate_references
from app.login_protection import LoginAttemptLimiter
from app.redis_state import SecurityStateUnavailable
from app.schemas.user import (
    ForgotPasswordRequest, ChangePasswordRequest, ResetPasswordRequest,
    SecurityQuestionResponse, UserRegister, UserRead, UserLogin,
    TokenResponse, CurrentUserRead,
)
from app.security import (
    auth_settings, hash_password, issue_access_token, normalize_security_answer,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])
audit_logger = logging.getLogger("hrms.security.audit")
login_limiter = LoginAttemptLimiter(
    max_attempts=auth_settings.login_max_attempts,
    window_seconds=auth_settings.login_window_seconds,
    lockout_seconds=auth_settings.login_lockout_seconds,
)


def _subject(username: str) -> str:
    return sha256(username.casefold().strip().encode("utf-8")).hexdigest()[:16]


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _audit(db: Session, event_type: str, *, actor_user_id: int | None = None, details=None) -> None:
    record_audit_event(db, event_type=event_type, actor_user_id=actor_user_id, details=details)
    db.commit()


def login_limit_keys(request: Request, username: str) -> tuple[str, str]:
    return f"ip:{_client_ip(request)}", f"account:{username.casefold().strip()}"


def reject_failed_login(request: Request, username: str, db: Session) -> None:
    keys = login_limit_keys(request, username)
    try:
        retry_after = login_limiter.record_failure(*keys)
    except SecurityStateUnavailable:
        raise HTTPException(503, "Authentication service is temporarily unavailable") from None
    _audit(db, "auth.login.failed", details={"subject": _subject(username), "ip": _client_ip(request)})
    audit_logger.warning("event=login_failed subject=%s ip=%s", _subject(username), _client_ip(request))
    if retry_after:
        _audit(db, "auth.login.locked", details={"subject": _subject(username), "ip": _client_ip(request), "retry_after": retry_after})
        raise HTTPException(429, "Too many login attempts. Try again later.", headers={"Retry-After": str(retry_after)})


def master_rows(rows):
    return [{column.name: getattr(row, column.name) for column in row.__table__.columns if column.name != "deleted_at"} for row in rows]


@router.get("/registration-options")
def registration_options(db: Session = Depends(get_db)):
    return {
        "divisions": master_rows(db.scalars(select(Division).order_by(Division.name)).all()),
        "departments": master_rows(db.scalars(select(Department).order_by(Department.name)).all()),
        "designations": master_rows(db.scalars(select(Designation).order_by(Designation.name)).all()),
        "locations": master_rows(db.scalars(select(Location).order_by(Location.name)).all()),
        "office_addresses": master_rows(db.scalars(select(OfficeAddress).order_by(OfficeAddress.city)).all()),
    }


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: UserRegister, db: Session = Depends(get_db), ring=Depends(get_employee_key_ring)):
    role = db.scalar(select(Role).where(Role.name == data.role))
    if role is None:
        raise HTTPException(503, f"{data.role.title()} role is not configured")
    employee = None
    if data.employee is not None:
        lock_employee_writes(db)
        validate_references(db, data.employee.model_dump())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        employee = Employee(**storage_values(data.employee, ring), created_at=now, updated_at=now)
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
        security_answer_hash=hash_password(normalize_security_answer(data.security_answer.get_secret_value())),
        approval_status="pending", role_id=role.id, employee_id=employee.id if employee is not None else None,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username or employee code is unavailable") from None
    db.refresh(user)
    _audit(db, "auth.registration.created", actor_user_id=user.id, details={"role": data.role})
    return user


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, response: Response, request: Request, db: Session = Depends(get_db)):
    keys = login_limit_keys(request, data.username)
    try:
        retry_after = login_limiter.blocked(*keys)
    except SecurityStateUnavailable:
        raise HTTPException(503, "Authentication service is temporarily unavailable") from None
    if retry_after:
        raise HTTPException(429, "Too many login attempts. Try again later.", headers={"Retry-After": str(retry_after)})
    user = db.scalar(select(User).where(User.username == data.username))
    if user is None or not verify_password(data.password.get_secret_value(), user.password_hash):
        reject_failed_login(request, data.username, db)
        raise HTTPException(401, "Invalid username or password")
    try:
        login_limiter.record_success(*keys)
    except SecurityStateUnavailable:
        raise HTTPException(503, "Authentication service is temporarily unavailable") from None
    if user.approval_status == "pending":
        raise HTTPException(403, "Your registration is awaiting administrator approval")
    if user.approval_status == "rejected":
        raise HTTPException(403, "Your registration was rejected by an administrator")
    issued = issue_access_token(user.id, user.session_version)
    try:
        token_state.activate(token_id=issued.token_id, expires_at=issued.expires_at)
    except SecurityStateUnavailable:
        raise HTTPException(503, "Authentication service is temporarily unavailable") from None
    _audit(db, "auth.login.succeeded", actor_user_id=user.id, details={"ip": _client_ip(request)})
    response.set_cookie(key="hrms_access_token", value=issued.value, httponly=True,
                        secure=auth_settings.cookie_secure, samesite="lax",
                        max_age=auth_settings.auth_session_idle_seconds, path="/")
    return TokenResponse(access_token=issued.value)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    payload = request.state.access_token_payload
    try:
        token_state.revoke(token_id=payload["jti"], expires_at=int(payload["exp"]))
    except SecurityStateUnavailable:
        raise HTTPException(503, "Authentication service is temporarily unavailable") from None
    _audit(db, "auth.logout", actor_user_id=current_user.id)
    response.delete_cookie(key="hrms_access_token", secure=auth_settings.cookie_secure, samesite="lax", path="/")


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
    user.session_version += 1
    db.commit()
    _audit(db, "auth.password.reset", actor_user_id=user.id)


@router.post("/change-password", status_code=204)
def change_password(data: ChangePasswordRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_password = data.current_password.get_secret_value()
    new_password = data.new_password.get_secret_value()
    if not verify_password(current_password, current_user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    if verify_password(new_password, current_user.password_hash):
        raise HTTPException(400, "New password must be different from the current password")
    current_user.password_hash = hash_password(new_password)
    current_user.session_version += 1
    db.commit()
    _audit(db, "auth.password.changed", actor_user_id=current_user.id)


@router.get("/me", response_model=CurrentUserRead)
def get_my_account(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    role = db.get(Role, current_user.role_id)
    if role is None:
        raise HTTPException(500, "User role is not configured")
    return CurrentUserRead(id=current_user.id, username=current_user.username, role_id=current_user.role_id,
                           employee_id=current_user.employee_id, approval_status=current_user.approval_status,
                           role=role.name)