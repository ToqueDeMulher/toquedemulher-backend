from pydantic import BaseModel, EmailStr
from typing import List
from app.schemas.payments import PaymentItem

class CreatePreferenceRequest(BaseModel):
    order_id: str
    payer_email: EmailStr
    items: List[PaymentItem]

class CreatePreferenceResponse(BaseModel):
    preference_id: str | None = None        # id da preferência criada no Mercado Pago
    init_point: str | None = None           # link do checkout
    sandbox_init_point: str | None = None   # link de teste/sandbox do checkout em ambiente de teste
    raw: dict | None = None                 # resposta bruta do Mercado Pago