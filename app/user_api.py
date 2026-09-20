from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models.role import Role
from app.models.user import User
from app.models.employee import Employee
from app.schemas.user import UserRead

router = APIRouter(prefix="/admin", tags=["User management"],
                   dependencies=[Depends(require_roles("admin"))])


class UserAccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["admin", "employee", "query"] | None = None
    employee_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide role or employee_id")
        if "role" in self.model_fields_set and self.role is None:
            raise ValueError("Role cannot be null")
        return self


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


@router.get("/roles", response_model=list[RoleRead])
def list_roles(db: Session = Depends(get_db)):
    return db.scalars(select(Role).where(Role.name.in_(("admin", "employee", "query"))).order_by(Role.id)).all()


@router.get("/users", response_model=list[UserRead])
def list_users(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id).offset(offset).limit(limit)).all()


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    return user


@router.post("/users/{user_id}/approve", response_model=UserRead)
def approve_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user(user_id, db)
    user.approval_status = "approved"
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reject", response_model=UserRead)
def reject_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user(user_id, db)
    role = db.get(Role, user.role_id)
    if role is not None and role.name == "admin":
        raise HTTPException(409, "Administrator accounts cannot be rejected")
    user.approval_status = "rejected"
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user_access(user_id: int, data: UserAccessUpdate, db: Session = Depends(get_db)):
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(72411921)"))
    user = get_user(user_id, db)
    if "role" in data.model_fields_set:
        role = db.scalar(select(Role).where(Role.name == data.role))
        if role is None:
            raise HTTPException(422, "Role is not configured")
        current_role = db.get(Role, user.role_id)
        if current_role and current_role.name == "admin" and role.name != "admin":
            another_admin = db.scalar(select(User.id).where(User.role_id == current_role.id, User.id != user.id).limit(1))
            if another_admin is None:
                raise HTTPException(409, "The last admin cannot be demoted")
        user.role_id = role.id
    if "employee_id" in data.model_fields_set:
        if data.employee_id is not None:
            employee = db.get(Employee, data.employee_id)
            if employee is None or employee.deleted_at is not None:
                raise HTTPException(422, "Employee must exist and not be deleted")
        user.employee_id = data.employee_id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Employee is already linked to another account") from None
    db.refresh(user)
    return user
