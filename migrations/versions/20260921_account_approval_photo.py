from alembic import op
import sqlalchemy as sa


revision = "20260921_account_approval_photo"
down_revision = "2641e7fd4a35"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("security_question", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("security_answer_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("approval_status", sa.String(length=20), nullable=True))
    op.execute("UPDATE users SET approval_status = 'approved'")
    op.alter_column("users", "approval_status", nullable=False, server_default="pending")
    op.add_column("employees", sa.Column("employee_photo", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("employees", "employee_photo")
    op.drop_column("users", "approval_status")
    op.drop_column("users", "security_answer_hash")
    op.drop_column("users", "security_question")
