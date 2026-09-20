from datetime import date, datetime
from enum import Enum
import base64
import binascii

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

class EmploymentType(str, Enum):
    INTERN = "intern"
    PERMANENT = "permanent"
    CONTRACT = "contract"
    TEMPORARY = "temporary"


class EmploymentStatus(str, Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    EXITED = "exited"

class EmployeeBase(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    employee_code: str = Field(min_length=1, max_length=30)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date
    personal_email: EmailStr
    work_email: EmailStr
    phone_number: str = Field(min_length=8, max_length=20)
    residential_address: str = Field(min_length=1, max_length=500)
    employee_photo: str | None = None
    date_of_joining: date
    employment_type: EmploymentType
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE
    division_id: int = Field(gt=0)
    department_id: int = Field(gt=0)
    designation_id: int = Field(gt=0)
    location_id: int = Field(gt=0)
    office_address_id: int = Field(gt=0)
    reporting_manager_id: int | None = Field(default=None, gt=0)

    @field_validator("employee_photo")
    @classmethod
    def validate_employee_photo(cls, value: str | None):
        if value is None:
            return value
        prefix, separator, encoded = value.partition(",")
        if not separator or prefix not in {
            "data:image/jpeg;base64",
            "data:image/png;base64",
            "data:image/webp;base64",
        }:
            raise ValueError("Photo must be a JPEG, PNG or WebP image")
        try:
            photo = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("Photo contains invalid base64 data") from None
        if not photo or len(photo) > 2 * 1024 * 1024:
            raise ValueError("Photo must be between 1 byte and 2 MB")
        return value
    @model_validator(mode="after")
    def validate_dates(self):
        if self.date_of_birth >= date.today():
            raise ValueError("Date of birth must be in the past")

        if self.date_of_birth >= self.date_of_joining:
            raise ValueError(
                "Date of birth must be before the date of joining"
            )

        return self

class EmployeeCreate(EmployeeBase):
    employee_code: str = Field(
        min_length=1,
        max_length=30,
        pattern=r"^[A-Za-z0-9]+$",
)

class EmployeeUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    employee_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
        pattern=r"^[A-Za-z0-9]+$",
    )

    first_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    last_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    date_of_birth: date | None = None
    personal_email: EmailStr | None = None
    work_email: EmailStr | None = None

    phone_number: str | None = Field(
        default=None,
        min_length=8,
        max_length=20,
    )

    residential_address: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )
    employee_photo: str | None = None
    date_of_joining: date | None = None
    employment_type: EmploymentType | None = None
    employment_status: EmploymentStatus | None = None
    division_id: int | None = Field(default=None, gt=0)
    department_id: int | None = Field(default=None, gt=0)
    designation_id: int | None = Field(default=None, gt=0)
    location_id: int | None = Field(default=None, gt=0)
    office_address_id: int | None = Field(default=None, gt=0)
    reporting_manager_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")

        return self

class EmployeeRead(EmployeeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)
    created_at: datetime
    updated_at: datetime

class EmployeeQueryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str
    date_of_joining: date
    employment_type: EmploymentType
    employment_status: EmploymentStatus
    division_id: int
    department_id: int
    designation_id: int
    location_id: int
    office_address_id: int
    reporting_manager_id: int | None
    created_at: datetime
    updated_at: datetime    
