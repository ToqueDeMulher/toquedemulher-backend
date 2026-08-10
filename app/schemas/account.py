from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AccountOrderItemResponse(BaseModel):
    id: str
    title: str
    quantity: int
    unit_price: float


class AccountOrderResponse(BaseModel):
    id: str
    order_date: datetime
    status: str
    total: float
    items_count: int
    items: list[AccountOrderItemResponse]


class AccountReviewResponse(BaseModel):
    id: int
    product_id: UUID
    product_name: str
    rating: int
    title: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime
