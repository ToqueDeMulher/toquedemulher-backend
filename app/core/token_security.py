from dataclasses import dataclass
import hashlib
import hmac
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.settings import settings


def password_fingerprint(password_hash: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(),
                    ('password-version:' + password_hash).encode(), hashlib.sha256).hexdigest()


def matches_password_fingerprint(candidate: object, password_hash: str) -> bool:
    return isinstance(candidate, str) and candidate.isascii() and hmac.compare_digest(
        candidate, password_fingerprint(password_hash))


@dataclass(frozen=True)
class EmailTokenData:
    email: str
    user_id: UUID
    password_version: str | None = None


def decode_email_token(token: str, token_type: str) -> EmailTokenData | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                             options={'require': ['exp', 'sub', 'uid', 'type']})
        if payload['type'] != token_type or not isinstance(payload['sub'], str):
            return None
        return EmailTokenData(email=payload['sub'], user_id=UUID(payload['uid']),
                              password_version=payload.get('pwd'))
    except (InvalidTokenError, ValueError, TypeError, AttributeError):
        return None
