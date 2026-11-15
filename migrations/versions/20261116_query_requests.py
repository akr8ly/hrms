"""add query request applications

Revision ID: 20261116_query_requests
Revises: 20261112_expense_receipt
Create Date: 2026-11-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20261116_query_requests"
down_revision = "20261112_expense_receipt"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "query_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("requester_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("subject", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("related_reference", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_query_requests_requester_user_id", "query_requests", ["requester_user_id"])
    op.create_index("ix_query_requests_category", "query_requests", ["category"])
    op.create_index("ix_query_requests_status", "query_requests", ["status"])


def downgrade():
    op.drop_table("query_requests")
