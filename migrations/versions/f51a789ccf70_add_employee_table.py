"""add employee table

Revision ID: f51a789ccf70
Revises: 6b5b549c130b
Create Date: 2026-09-09 17:36:47.775806

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f51a789ccf70'
down_revision: Union[str, Sequence[str], None] = '6b5b549c130b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('employees',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('employee_code', sa.String(length=30), nullable=False),
    sa.Column('first_name', sa.Text(), nullable=False),
    sa.Column('last_name', sa.Text(), nullable=False),
    sa.Column('date_of_birth', sa.Text(), nullable=False),
    sa.Column('personal_email', sa.Text(), nullable=False),
    sa.Column('work_email', sa.Text(), nullable=False),
    sa.Column('phone_number', sa.Text(), nullable=False),
    sa.Column('residential_address', sa.Text(), nullable=False),
    sa.Column('date_of_joining', sa.Date(), nullable=False),
    sa.Column('employment_type', sa.String(length=20), nullable=False),
    sa.Column('employment_status', sa.String(length=20), nullable=False),
    sa.Column('division_id', sa.Integer(), nullable=False),
    sa.Column('department_id', sa.Integer(), nullable=False),
    sa.Column('designation_id', sa.Integer(), nullable=False),
    sa.Column('location_id', sa.Integer(), nullable=False),
    sa.Column('office_address_id', sa.Integer(), nullable=False),
    sa.Column('reporting_manager_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
    sa.ForeignKeyConstraint(['designation_id'], ['designations.id'], ),
    sa.ForeignKeyConstraint(['division_id'], ['divisions.id'], ),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
    sa.ForeignKeyConstraint(['office_address_id'], ['office_addresses.id'], ),
    sa.ForeignKeyConstraint(['reporting_manager_id'], ['employees.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('employee_code')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('employees')
