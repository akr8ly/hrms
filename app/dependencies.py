import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.security import auth_settings
from app.models.role import Role

bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired login token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
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

