import jwt
from fastapi import Cookie, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth_state import token_state
from app.database import get_db
from app.models.role import Role
from app.models.user import User
from app.redis_state import SecurityStateUnavailable
from app.security import auth_settings

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    cookie_token: str | None = Cookie(default=None, alias="hrms_access_token"),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired login token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None and cookie_token is None:
        raise unauthorized

    if credentials is None and request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") not in auth_settings.frontend_origins:
            raise HTTPException(403, "Request origin is not allowed")

    try:
        payload = jwt.decode(
            credentials.credentials if credentials is not None else cookie_token,
            auth_settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp", "jti", "sv"]},
        )
        user_id = int(payload["sub"])
        token_id = str(payload["jti"])
        session_version = int(payload["sv"])
        expires_at = int(payload["exp"])
        if user_id <= 0 or len(token_id) < 16 or session_version < 0:
            raise ValueError("Invalid token identity")
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise unauthorized from None

    try:
        if not token_state.validate_and_touch(
            token_id=token_id,
            expires_at=expires_at,
        ):
            raise unauthorized
    except SecurityStateUnavailable:
        raise HTTPException(503, "Authentication service is temporarily unavailable") from None

    user = db.get(User, user_id)
    if user is None or user.session_version != session_version:
        raise unauthorized
    if user.approval_status != "approved":
        raise HTTPException(403, "Your account is awaiting administrator approval")

    request.state.access_token_payload = payload
    request.state.authenticated_user_id = user.id
    return user


def require_roles(*allowed_roles: str):
    def check_role(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        role = db.get(Role, current_user.role_id)
        if role is None or role.name not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission for this action",
            )
        return current_user

    return check_role