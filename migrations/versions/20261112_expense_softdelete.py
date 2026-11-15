"""add inherited soft-delete columns to expense tables

Revision ID: 20261112_expense_softdelete
Revises: 20261112_expense_reimbursement
Create Date: 2026-11-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20261112_expense_softdelete"
down_revision = "20261112_expense_reimbursement"
branch_labels = None
depends_on = None


TABLES = ("expense_claims", "expense_entries", "expense_claim_approvals")


def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade():
    for table in reversed(TABLES):
        op.drop_column(table, "deleted_at")
