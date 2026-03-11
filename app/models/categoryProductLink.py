from uuid import UUID
from sqlmodel import SQLModel, Field


class CategoryProductLink(SQLModel, table=True):
    category_id: int = Field(foreign_key="category.id", primary_key=True)
    product_id: UUID = Field(foreign_key="product.id", primary_key=True)