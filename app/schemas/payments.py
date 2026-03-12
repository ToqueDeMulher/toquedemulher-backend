from pydantic import BaseModel, EmailStr
from typing import List

class PaymentItem(BaseModel):
    id: str
    title: str
    quantity: int
    unit_price: float

class CreatePreferenceRequest(BaseModel):
    order_id: str
    payer_email: EmailStr
    items: List[PaymentItem]

class CreatePreferenceResponse(BaseModel):
    preference_id: str | None = None
    init_point: str | None = None
    sandbox_init_point: str | None = None