from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


QueryCategory = Literal["employee_related", "application_usage", "reimbursement_report", "llm_calls"]
QueryStatus = Literal["submitted", "in_review", "resolved", "closed"]


class QueryRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: QueryCategory
    subject: str = Field(min_length=4, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    related_reference: str | None = Field(default=None, max_length=100)


class QueryRequestRead(BaseModel):
    id: int
    category: QueryCategory
    subject: str
    description: str
    related_reference: str | None
    status: QueryStatus
    created_at: datetime
    updated_at: datetime


class AdminQueryRequestRead(QueryRequestRead):
    sender: str
