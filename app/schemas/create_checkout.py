from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CheckoutItem(BaseModel):
    id: Optional[str] = None
    slug: Optional[str] = None
    name: str
    product_url: str
    unit_price: float = Field(gt=0)
    quantity: int = Field(gt=0)

class CreateCheckoutRequest(BaseModel):
    address_id: UUID
    items: List[CheckoutItem]


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    client_secret: Optional[str] = None
