from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class QueryRequest(Base):
    __tablename__ = "query_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    requester_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    related_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Expense queries may optionally be tied to a claim.  Keeping this nullable
    # preserves existing, general reimbursement enquiries as pending review.
    expense_claim_id: Mapped[int | None] = mapped_column(ForeignKey("expense_claims.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="submitted", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
