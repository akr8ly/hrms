"""link reimbursement queries to expense claims

Revision ID: 20261117_expense_query_link
Revises: 20261116_query_requests
Create Date: 2026-11-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20261117_expense_query_link"
down_revision = "20261116_query_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("query_requests", sa.Column("expense_claim_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_query_requests_expense_claim_id",
        "query_requests",
        "expense_claims",
        ["expense_claim_id"],
        ["id"],
    )
    op.create_index("ix_query_requests_expense_claim_id", "query_requests", ["expense_claim_id"])


def downgrade():
    op.drop_index("ix_query_requests_expense_claim_id", table_name="query_requests")
    op.drop_constraint("fk_query_requests_expense_claim_id", "query_requests", type_="foreignkey")
    op.drop_column("query_requests", "expense_claim_id")
