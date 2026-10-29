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


def normalize_security_answer(answer: str) -> str:
    return " ".join(answer.casefold().strip().split())

class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        hide_input_in_errors=True,
    )

    jwt_secret_key: SecretStr = Field(min_length=32)
    auth_cookie_secure: bool = False
    enforce_https: bool = False
    hsts_max_age_seconds: int = Field(default=31_536_000, ge=0)
    trust_proxy_headers: bool = False
    allowed_frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    login_max_attempts: int = Field(default=5, ge=3, le=20)
    login_window_seconds: int = Field(default=900, ge=60, le=86_400)
    login_lockout_seconds: int = Field(default=900, ge=60, le=86_400)

    @property
    def frontend_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_frontend_origins.split(",") if origin.strip()]

    @property
    def cookie_secure(self) -> bool:
        return self.auth_cookie_secure or self.enforce_https


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
