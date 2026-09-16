from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone

import jwt
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return password_hasher.verify(password, stored_hash)

class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    jwt_secret_key: SecretStr = Field(min_length=32)


auth_settings = AuthSettings()

def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=30),
    }

    return jwt.encode(
        payload,
        auth_settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )