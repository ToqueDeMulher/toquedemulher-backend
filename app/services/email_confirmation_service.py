from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID

import jwt

from app.core.settings import ROOT_DIR, settings
from app.core.token_security import EmailTokenData, decode_email_token
from app.services.email_service import send_email


TOKEN_TYPE = "email_confirmation"


def create_email_confirmation_token(email: str, *, user_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.EMAIL_CONFIRMATION_EXPIRE_MINUTES
    )
    payload = {
        "sub": email,
        "type": TOKEN_TYPE,
        "exp": expire,
        "uid": str(user_id),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_email_confirmation_token(token: str) -> EmailTokenData | None:
    return decode_email_token(token, TOKEN_TYPE)


def build_email_confirmation_url(token: str) -> str:
    query = urlencode({"token": token})
    return f"{settings.FRONTEND_URL.rstrip('/')}/confirm-email?{query}"


def render_confirmation_template(confirmation_url: str, email: str) -> str:
    template_path = Path(settings.EMAIL_CONFIRMATION_TEMPLATE_PATH)
    if not template_path.is_absolute():
        template_path = ROOT_DIR / template_path

    html = template_path.read_text(encoding="utf-8")
    replacements = {
        "{{ .ConfirmationURL }}": confirmation_url,
        "{{ .SiteURL }}": settings.FRONTEND_URL.rstrip("/"),
        "{{ .Email }}": email,
    }

    for key, value in replacements.items():
        html = html.replace(key, value)

    return html


def send_confirmation_email(user_name: str, user_email: str, user_id: UUID) -> bool:
    token = create_email_confirmation_token(user_email, user_id=user_id)
    confirmation_url = build_email_confirmation_url(token)
    html_body = render_confirmation_template(confirmation_url, user_email)
    text_body = (
        f"Ola, {user_name}. Confirme seu email para finalizar o cadastro: "
        f"{confirmation_url}"
    )

    return send_email(
        to_email=user_email,
        subject="Confirm your email address",
        html_body=html_body,
        text_body=text_body,
    )
