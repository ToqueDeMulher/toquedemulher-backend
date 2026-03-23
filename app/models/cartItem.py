from typing import Optional 
from uuid import UUID
from datetime import datetime
from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now
from app.models.product import Product
from app.models.cart import Cart


class CartItem(SQLModel, table=True):
    __tablename__ = "cart_item"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_cart_item_quantity_non_negative"),
        CheckConstraint("unit_price_at_time >= 0", name="ck_cart_item_unit_price_non_negative"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    cart_id: UUID = Field(foreign_key="cart.id", index=True)
    product_id: UUID = Field(foreign_key="product.id", index=True)

    quantity: int
    unit_price_at_time: float
    created_at: datetime = Field(default_factory=utc_now)

    cart: Optional[Cart] = Relationship(back_populates="items")
    product: Optional["Product"] = Relationship(back_populates="cart_items")