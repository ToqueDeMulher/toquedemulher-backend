from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CartItemAdd(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1


class CartItemUpdate(BaseModel):
    quantity: int


class CartItemOut(BaseModel):
    id: int
    product_id: int
    variant_id: Optional[int] = None
    quantity: int
    unit_price: float
    subtotal: float
    product_name: Optional[str] = None
    product_image: Optional[str] = None
    variant_name: Optional[str] = None

    class Config:
        from_attributes = True


class CartOut(BaseModel):
    id: int
    user_id: int
    items: List[CartItemOut] = []
    total: float
    item_count: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
