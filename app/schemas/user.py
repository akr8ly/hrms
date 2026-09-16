from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from typing import Literal

from app.schemas.employee import EmployeeCreate

class UserRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_]+$",
    )

    password: SecretStr = Field(
        min_length=15,
        max_length=128,
    )

    role: Literal["employee", "query"]
    employee: EmployeeCreate | None = None

    @model_validator(mode="after")
    def validate_role_profile(self):
        if self.role == "employee" and self.employee is None:
            raise ValueError("Employee profile is required for the Employee role")
        if self.role == "query" and self.employee is not None:
            raise ValueError("Employee profile is not allowed for the Query role")
        return self

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role_id: int
    employee_id: int | None

class CurrentUserRead(UserRead):
    role: Literal["admin", "employee", "query"]

class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50)
    password: SecretStr = Field(min_length=1, max_length=128)
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"

  
