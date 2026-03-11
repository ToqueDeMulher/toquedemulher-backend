from typing import  Optional
from uuid import UUID
from datetime import datetime, date
from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now

class Stock(SQLModel, table=True):
    __tablename__ = "stock"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_stock_quantity_non_negative"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: UUID = Field(foreign_key="product.id", index=True)

    quantity: int
    expiry_date: Optional[date] = None
    last_update: datetime = Field(default_factory=utc_now)
    last_quantity: Optional[int] = None

    product: Optional["Product"] = Relationship(back_populates="stock_items") #type: ignore