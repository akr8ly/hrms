from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
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
        min_length=7,
        max_length=15,
    )

    role: Literal["employee", "query"]
    employee: EmployeeCreate | None = None
    security_question: Literal["birthplace", "first_school", "childhood_nickname"]
    security_answer: SecretStr = Field(min_length=2, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_policy(cls, password: SecretStr):
        value = password.get_secret_value()
        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain at least one digit")
        if not any(not character.isalnum() for character in value):
            raise ValueError("Password must contain at least one special character")
        return password

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
    approval_status: Literal["pending", "approved", "rejected"]

class CurrentUserRead(UserRead):
    role: Literal["admin", "employee", "query"]

class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50)
    password: SecretStr = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=50)


class SecurityQuestionResponse(BaseModel):
    security_question: Literal["birthplace", "first_school", "childhood_nickname"]


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=50)
    security_answer: SecretStr = Field(min_length=2, max_length=100)
    new_password: SecretStr = Field(min_length=7, max_length=15)

    @field_validator("new_password")
    @classmethod
    def validate_password_policy(cls, password: SecretStr):
        value = password.get_secret_value()
        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain at least one digit")
        if not any(not character.isalnum() for character in value):
            raise ValueError("Password must contain at least one special character")
        return password


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=7, max_length=15)

    @field_validator("new_password")
    @classmethod
    def validate_password_policy(cls, password: SecretStr):
        value = password.get_secret_value()
        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain at least one digit")
        if not any(not character.isalnum() for character in value):
            raise ValueError("Password must contain at least one special character")
        return password
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"

  
