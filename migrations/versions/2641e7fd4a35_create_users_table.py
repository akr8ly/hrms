"""create users table

Revision ID: 2641e7fd4a35
Revises: 7621c2d658ba
Create Date: 2026-09-15 19:31:20.814619

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2641e7fd4a35'
down_revision: Union[str, Sequence[str], None] = '7621c2d658ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=50), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('employee_id'),
    sa.UniqueConstraint('username')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('users')
