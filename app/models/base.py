from datetime import datetime
from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
