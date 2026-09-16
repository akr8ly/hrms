from getpass import getpass

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.security import hash_password


class AdminSetup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    password: SecretStr = Field(min_length=15, max_length=128)


def create_first_admin(db, data):
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(72411921)"))
    role = db.scalar(select(Role).where(Role.name == "admin"))
    if role is None:
        raise ValueError("Create the admin role before running setup")
    if db.scalar(select(User.id).where(User.role_id == role.id).limit(1)) is not None:
        raise ValueError("An admin already exists; use admin user management")
    if db.scalar(select(User.id).where(User.username == data.username).execution_options(include_deleted=True)) is not None:
        raise ValueError("Choose a new username; existing accounts are not promoted by setup")
    user = User(username=data.username, password_hash=hash_password(data.password.get_secret_value()),
                role_id=role.id, employee_id=None)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("Username unavailable") from None
    return user


def main():
    print("First admin setup. Choose your own password; input is hidden.")
    username = input("New admin username: ").strip()
    password = getpass("Password (15-128 characters): ")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    try:
        data = AdminSetup(username=username, password=password)
    except ValidationError:
        raise SystemExit("Use a 3-50 character username (letters, digits, underscores) and a 15-128 character password") from None
    try:
        with SessionLocal() as db:
            user = create_first_admin(db, data)
            print(f"Admin account created: {user.username}. Sign in through /auth/login.")
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
