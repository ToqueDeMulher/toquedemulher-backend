from decimal import Decimal
from pydantic import BaseModel
from uuid import UUID
from typing import List

class CheckoutProductRequest(BaseModel):
    id: UUID
    name: str
    product_url: str
    unit_price: Decimal
    quantity: int

class CreateCheckoutRequest(BaseModel): 
    address_id: UUID
    items: List[CheckoutProductRequest]

class CheckoutResponse(BaseModel):
    checkout_url: str
