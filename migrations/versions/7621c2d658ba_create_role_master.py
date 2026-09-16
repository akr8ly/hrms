"""create role master

Revision ID: 7621c2d658ba
Revises: 20260915_soft_delete
Create Date: 2026-09-15 19:26:44.055446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7621c2d658ba'
down_revision: Union[str, Sequence[str], None] = '20260915_soft_delete'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('roles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=20), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('roles')
