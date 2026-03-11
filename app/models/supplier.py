from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship



class Supplier(SQLModel, table=True):
    __tablename__ = "supplier"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    contact: Optional[str] = None
    email: Optional[str] = Field(default=None, index=True)

    products: List["Product"] = Relationship(back_populates="supplier") #type: ignore
