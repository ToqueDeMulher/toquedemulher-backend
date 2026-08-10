from pydantic import BaseModel
from uuid import UUID
from typing import List
from pydantic import Field


class CheckoutItem(BaseModel):
    id: UUID
    name: str
    product_url: str
    unit_price: float = Field(gt=0)
    quantity: int = Field(gt=0)
    slug: str

class CreateCheckoutRequest(BaseModel):
    address_id: UUID
    items: List[CheckoutItem]

class CheckoutResponse(BaseModel):
    client_secret: str
    session_id: str
