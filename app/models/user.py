from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )
    
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    security_question: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    security_answer_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id"),
        nullable=False,
    )

    employee_id: Mapped[int | None] = mapped_column(
        ForeignKey("employees.id"),
        unique=True,
        nullable=True,
    )
