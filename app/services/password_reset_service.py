from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

from app.core.settings import settings
from app.core.token_security import EmailTokenData, decode_email_token, password_fingerprint
from app.services.email_service import send_password_reset_email

TOKEN_TYPE = "password_reset"
TOKEN_EXPIRE_MINUTES = 60


def create_password_reset_token(email: str, *, user_id: UUID, password_hash: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": email,
        "type": TOKEN_TYPE,
        "exp": expire,
        "uid": str(user_id),
        "pwd": password_fingerprint(password_hash),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password_reset_token(token: str) -> EmailTokenData | None:
    return decode_email_token(token, TOKEN_TYPE)


def send_password_reset_flow(user_name: str, user_email: str, user_id: UUID,
                             password_hash: str) -> bool:
    token = create_password_reset_token(user_email, user_id=user_id, password_hash=password_hash)
    return send_password_reset_email(user_email, user_name, token)
