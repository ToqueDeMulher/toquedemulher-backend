from pydantic import BaseModel
from typing import List


class PaymentItem(BaseModel):
    title: str
    quantity: int
    unit_price: float


class CreateCheckoutRequest(BaseModel):
    payer_email: str
    items: List[PaymentItem]


class CheckoutResponse(BaseModel):
    checkout_url: str
    order_id: str