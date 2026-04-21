from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship



class Supplier(SQLModel, table=True):
    __tablename__ = "supplier"

    id: int = Field(default=None, primary_key=True)

    name: str = Field(index=True)
    contact: Optional[str] = None
    email: Optional[str] = Field(default=None, index=True)

    batches: List["StockBatch"] = Relationship(back_populates="supplier") #type: ignore
    supplier_products: List["SupplierProduct"] = Relationship(back_populates="supplier") #type: ignore
    products: list["Product"] = Relationship(back_populates="supplier") #type: ignore
