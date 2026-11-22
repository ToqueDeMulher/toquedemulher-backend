from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.shipping import ShippingSelection


class CheckoutItem(BaseModel):
    id: str
    slug: str | None = None
    name: str = ""
    product_url: str = ""
    unit_price: float | None = Field(default=None, ge=0)
    quantity: int = Field(gt=0, le=100)


class CreateCheckoutRequest(BaseModel):
    address_id: UUID
    idempotency_key: UUID
    items: list[CheckoutItem] = Field(min_length=1, max_length=100)
    method: Literal["PIX", "CARD"] = "PIX"
    shipping: ShippingSelection | None = None
    coupon_code: str | None = Field(default=None, min_length=1, max_length=50)


class PixDetails(BaseModel):
    code: str
    image: str
    expires_at: datetime


class CheckoutResponse(BaseModel):
    checkout_url: str | None = None
    session_id: str
    order_id: UUID
    client_secret: str | None = None


class CheckoutStatusResponse(BaseModel):
    session_id: str
    order_id: UUID
    status: str
    amount: float
    discount_amount: float = 0
    currency: str
    pix: PixDetails | None = None
    checkout_url: str | None = None
