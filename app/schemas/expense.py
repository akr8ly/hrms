from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.employee import validate_employee_photo_data


ExpenseCategory = Literal["travel", "meals", "accommodation", "local_transport", "supplies", "other"]
ClaimStatus = Literal["draft", "submitted", "l1_approved", "l1_rejected", "l2_approved", "l2_rejected", "reimbursed"]


class ExpenseEntryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    expense_date: date
    category: ExpenseCategory
    description: str = Field(min_length=3, max_length=300)
    requested_amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    receipt_image: str | None = None

    @field_validator("expense_date")
    @classmethod
    def cannot_be_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Expense date cannot be in the future")
        return value

    @field_validator("receipt_image")
    @classmethod
    def validate_receipt_image(cls, value: str | None) -> str | None:
        return validate_employee_photo_data(value)


class ExpenseClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    cost_center: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9 _.-]+$")
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")
    entries: list[ExpenseEntryInput] = Field(min_length=1, max_length=5)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class ExpenseClaimUpdate(ExpenseClaimCreate):
    pass


class ExpenseDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: Literal["approved", "rejected"]
    remarks: str | None = Field(default=None, max_length=500)
    approved_amounts: list[Decimal] | None = None

    @field_validator("approved_amounts")
    @classmethod
    def valid_amounts(cls, values: list[Decimal] | None) -> list[Decimal] | None:
        if values is not None and any(value < 0 for value in values):
            raise ValueError("Approved amounts cannot be negative")
        return values

    @model_validator(mode="after")
    def decision_requirements(self):
        if self.action == "rejected" and not self.remarks:
            raise ValueError("Rejection remarks are required")
        return self


class ExpenseEntryRead(ExpenseEntryInput):
    id: int
    approved_amount: Decimal | None = None


class ExpenseApprovalRead(BaseModel):
    approval_level: int
    action: str
    approver_user_id: int
    remarks: str | None
    approved_total: Decimal | None
    decided_at: datetime


class ExpenseClaimRead(BaseModel):
    id: int
    claimant_employee_id: int
    cost_center: str
    currency: str
    status: ClaimStatus
    requested_total: Decimal
    l1_approved_total: Decimal | None
    l2_approved_total: Decimal | None
    entries: list[ExpenseEntryRead]
    approvals: list[ExpenseApprovalRead]
    created_at: datetime
    updated_at: datetime
