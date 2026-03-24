from typing import Optional 
from uuid import UUID
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now


class CartItem(SQLModel, table=True):
    __tablename__ = "cart_item"

    id: Optional[int] = Field(default=None, primary_key=True)
    cart_id: UUID = Field(foreign_key="cart.id", index=True)
    product_id: UUID = Field(foreign_key="product.id", index=True)

    quantity: int
    unit_price_at_time: float
    created_at: datetime = Field(default_factory=utc_now)

    cart: Optional["Cart"] = Relationship(back_populates="items")
    product: Optional["Product"] = Relationship(back_populates="cart_items")