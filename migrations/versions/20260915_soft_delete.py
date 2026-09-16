"""Preserve deleted master and employee records."""
from alembic import op
import sqlalchemy as sa

revision = "20260915_soft_delete"
down_revision = "f51a789ccf70"
branch_labels = None
depends_on = None

TABLES = ("divisions", "departments", "designations", "locations", "office_addresses", "employees")

def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(), nullable=True))

def downgrade():
    for table in reversed(TABLES):
        op.drop_column(table, "deleted_at")
