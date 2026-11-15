"""add encrypted receipt storage for expense entries

Revision ID: 20261112_expense_receipt
Revises: 20261112_expense_softdelete
Create Date: 2026-11-12
"""

from alembic import op
import sqlalchemy as sa


revision = "20261112_expense_receipt"
down_revision = "20261112_expense_softdelete"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("expense_entries", sa.Column("receipt_data", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("expense_entries", "receipt_data")
