"""add expense reimbursement workflow

Revision ID: 20261112_expense_reimbursement
Revises: 20261103_security_state_audit
Create Date: 2026-11-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20261112_expense_reimbursement"
down_revision = "20261103_security_state_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "expense_claims",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("claimant_employee_id", sa.Integer(), nullable=False),
        sa.Column("cost_center", sa.String(length=50), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("l1_approved_total", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("l2_approved_total", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["claimant_employee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expense_claims_claimant_employee_id", "expense_claims", ["claimant_employee_id"])
    op.create_index("ix_expense_claims_status", "expense_claims", ["status"])
    op.create_table(
        "expense_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("expense_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("requested_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("approved_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["expense_claims.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expense_entries_claim_id", "expense_entries", ["claim_id"])
    op.create_table(
        "expense_claim_approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("claim_id", sa.Integer(), nullable=False),
        sa.Column("approval_level", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("approver_user_id", sa.Integer(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("approved_total", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["expense_claims.id"]),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", "approval_level", name="uq_expense_claim_approval_level"),
    )
    op.create_index("ix_expense_claim_approvals_claim_id", "expense_claim_approvals", ["claim_id"])


def downgrade():
    op.drop_index("ix_expense_claim_approvals_claim_id", table_name="expense_claim_approvals")
    op.drop_table("expense_claim_approvals")
    op.drop_index("ix_expense_entries_claim_id", table_name="expense_entries")
    op.drop_table("expense_entries")
    op.drop_index("ix_expense_claims_status", table_name="expense_claims")
    op.drop_index("ix_expense_claims_claimant_employee_id", table_name="expense_claims")
    op.drop_table("expense_claims")
