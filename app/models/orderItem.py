from typing import Optional 
from uuid import UUID
from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship
from app.models.product import Product
from app.models.order import Order

class OrderItem(SQLModel, table=True):
    __tablename__ = "order_item"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_order_item_quantity_non_negative"),
        CheckConstraint("unit_price_at_time >= 0", name="ck_order_item_unit_price_non_negative"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    product_id: UUID = Field(foreign_key="product.id", index=True)

    quantity: int
    unit_price_at_time: float

    order: Optional[Order] = Relationship(back_populates="items")
    product: Optional["Product"] = Relationship(back_populates="order_items")