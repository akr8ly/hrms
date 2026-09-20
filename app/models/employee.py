from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    employee_code: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    date_of_birth: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    personal_email: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    work_email: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    phone_number: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    residential_address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    employee_photo: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    date_of_joining: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    employment_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    employment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )
    division_id: Mapped[int] = mapped_column(
        ForeignKey("divisions.id"),
        nullable=False,
    )

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"),
        nullable=False,
    )

    designation_id: Mapped[int] = mapped_column(
        ForeignKey("designations.id"),
        nullable=False,
    )

    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id"),
        nullable=False,
    )

    office_address_id: Mapped[int] = mapped_column(
        ForeignKey("office_addresses.id"),
        nullable=False,
    )

    reporting_manager_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
    
