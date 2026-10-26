import jwt
from fastapi import Cookie, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security import auth_settings
from app.models.role import Role

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

    # Cookie authentication is used by the browser. Protect unsafe requests
    # against cross-site submission while retaining bearer auth for Swagger
    # and external API clients.
    if credentials is None and request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") not in auth_settings.frontend_origins:
            raise HTTPException(403, "Request origin is not allowed")

    try:
        payload = jwt.decode(
            credentials.credentials if credentials is not None else cookie_token,
            auth_settings.jwt_secret_key.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "iat", "exp"]},
        )

        user_id = int(payload["sub"])
        if user_id <= 0:
            raise ValueError("Invalid user ID")

    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized from None

    user = db.get(User, user_id)

    if user is None:
        raise unauthorized

    if user.approval_status != "approved":
        raise HTTPException(403, "Your account is awaiting administrator approval")

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

