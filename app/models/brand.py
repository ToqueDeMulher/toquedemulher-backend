from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship


class Brand(SQLModel, table=True):
    __tablename__ = "brand"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    products: List["Product"] = Relationship(back_populates="brand") #type: ignore