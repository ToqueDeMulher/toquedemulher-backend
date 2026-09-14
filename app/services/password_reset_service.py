from datetime import datetime, timedelta, timezone

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.settings import settings
from app.services.email_service import send_password_reset_email

TOKEN_TYPE = "password_reset"
TOKEN_EXPIRE_MINUTES = 60


def create_password_reset_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "type": TOKEN_TYPE,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password_reset_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
    except InvalidTokenError:
        return None

    if payload.get("type") != TOKEN_TYPE:
        return None

    email = payload.get("sub")
    return str(email) if email else None


def send_password_reset_flow(user_name: str, user_email: str) -> bool:
    token = create_password_reset_token(user_email)
    return send_password_reset_email(user_email, user_name, token)
