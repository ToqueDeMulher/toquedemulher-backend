from typing import  Optional
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now

class SupplierProduct(SQLModel, table=True):
    __tablename__ = "supplier_product"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    supplier_id: int = Field(foreign_key="supplier.id")
    product_id: UUID = Field(foreign_key="product.id")

    supplier_price: float  # preço do fornecedor
    lead_time_days: Optional[int] = None

    created_at: datetime = Field(default_factory=utc_now)

    supplier: Optional["Supplier"] = Relationship(back_populates="supplier_products") #type: ignore
    product: Optional["Product"] = Relationship(back_populates="supplier_products") #type: ignore