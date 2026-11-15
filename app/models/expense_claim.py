from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExpenseClaim(Base):
    __tablename__ = "expense_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claimant_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    cost_center: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", index=True)
    l1_approved_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    l2_approved_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ExpenseEntry(Base):
    __tablename__ = "expense_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("expense_claims.id"), nullable=False, index=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    requested_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    receipt_data: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExpenseClaimApproval(Base):
    __tablename__ = "expense_claim_approvals"
    __table_args__ = (UniqueConstraint("claim_id", "approval_level", name="uq_expense_claim_approval_level"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("expense_claims.id"), nullable=False, index=True)
    approval_level: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    approver_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
