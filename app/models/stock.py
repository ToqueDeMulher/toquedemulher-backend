from typing import  Optional
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now
from typing import List

class Stock(SQLModel, table=True):
    __tablename__ = "stock"

    __table_args__ = (
        CheckConstraint("total_quantity >= 0", name="ck_stock_quantity_non_negative"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: UUID = Field(foreign_key="product.id", index=True, unique=True)

    total_quantity: int = 0
    updated_at: datetime = Field(default_factory=utc_now)

    product: Optional["Product"] = Relationship(back_populates="stock") #type: ignore
    batches: List["StockBatch"] = Relationship(back_populates="stock") #type: ignore