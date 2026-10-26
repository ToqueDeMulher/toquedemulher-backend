from html import escape

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.settings import settings
from app.services.brasil_api import check_rate_limit
from app.services.email_service import send_email

router = APIRouter(tags=["store"])


class ContactRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    subject: str = Field(min_length=2, max_length=120, pattern=r"^[^\r\n]+$")
    message: str = Field(min_length=10, max_length=5000)


@router.get("/store")
def store_configuration():
    return {
        "contact_email": settings.STORE_CONTACT_EMAIL or None,
        "free_shipping_threshold": settings.MELHOR_ENVIO_FREE_SHIPPING_THRESHOLD,
    }


@router.post("/contact", status_code=202)
def contact(payload: ContactRequest, request: Request):
    check_rate_limit(request, "contact")
    if not settings.CONTACT_RECIPIENT_EMAIL:
        raise HTTPException(503, "Atendimento indisponível no momento. Tente novamente mais tarde.")
    text = f"Nome: {payload.name}\nE-mail: {payload.email}\nAssunto: {payload.subject}\n\n{payload.message}"
    accepted = send_email(
        settings.CONTACT_RECIPIENT_EMAIL,
        "Mensagem recebida pelo site",
        f"<pre>{escape(text)}</pre>",
        text,
    )
    if not accepted:
        raise HTTPException(503, "Não foi possível enviar sua mensagem. Tente novamente.")
    return {"message": "Mensagem enviada. Obrigada por entrar em contato."}
