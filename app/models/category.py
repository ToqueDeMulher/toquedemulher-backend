from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship
from app.models.categoryProductLink import CategoryProductLink

class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    products: List["Product"] = Relationship( #type: ignore
        back_populates="categories",
        link_model=CategoryProductLink,
    )