from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, with_loader_criteria
from app.models.base import Base


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    database_url: str


settings = Settings()


engine = create_engine(
    settings.database_url,
    echo=False,
    hide_parameters=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


@event.listens_for(Session, "do_orm_execute")
def hide_deleted_records(state):
    if state.is_select and not state.execution_options.get("include_deleted", False):
        state.statement = state.statement.options(
            with_loader_criteria(Base, lambda model: model.deleted_at.is_(None), include_aliases=True)
        )


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
