from typing import  Optional
from uuid import UUID, uuid4
from datetime import datetime, date
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now

class StockBatch(SQLModel, table=True):
    __tablename__ = "stock_batch"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    product_id: UUID = Field(foreign_key="product.id", index=True)
    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")
    stock_id: UUID = Field(foreign_key="stock.id")

    quantity: int = Field(ge=0)
    unit_cost: float  

    expiry_date: Optional[date] = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    product: Optional["Product"] = Relationship(back_populates="batches") #type: ignore
    stock: Optional["Stock"] = Relationship(back_populates="batches") #type: ignore 
    supplier: Optional["Supplier"] = Relationship(back_populates="batches") #type: ignore