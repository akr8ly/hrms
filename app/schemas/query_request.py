from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


QueryCategory = Literal["employee_related", "application_usage", "reimbursement_report", "llm_calls"]
QueryStatus = Literal["submitted", "in_review", "resolved", "closed"]


class QueryRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: QueryCategory
    subject: str = Field(min_length=4, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    related_reference: str | None = Field(default=None, max_length=100)
    expense_claim_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_expense_claim_reference(self):
        if self.expense_claim_id is not None and self.category != "reimbursement_report":
            raise ValueError("An expense claim can only be linked to a reimbursement query")
        return self


class QueryRequestRead(BaseModel):
    id: int
    category: QueryCategory
    subject: str
    description: str
    related_reference: str | None
    expense_claim_id: int | None
    status: QueryStatus
    created_at: datetime
    updated_at: datetime


class AdminQueryRequestRead(QueryRequestRead):
    sender: str


class AdminExpenseQueryRequestRead(AdminQueryRequestRead):
    claim_status: str | None = None
    cost_center: str | None = None
    currency: str | None = None
