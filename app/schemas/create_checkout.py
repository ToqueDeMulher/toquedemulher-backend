from pydantic import BaseModel
from uuid import UUID
from typing import List
from pydantic import Field


class Products(BaseModel):
    id: UUID
    name: str
    product_url: str
    quantity: int = Field(gt=0)
    slug: str

class CreateCheckoutRequest(BaseModel): 
    address_id: UUID
    items: List[Products]

class CheckoutResponse(BaseModel):
    client_secret: str
    session_id: str
