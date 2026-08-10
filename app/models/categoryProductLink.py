from uuid import UUID
from sqlalchemy import Index
from sqlmodel import SQLModel, Field


class CategoryProductLink(SQLModel, table=True):
    __table_args__ = (
        Index("ix_categoryproductlink_product_id", "product_id"),
    )

    category_id: int = Field(foreign_key="category.id", primary_key=True)
    product_id: UUID = Field(foreign_key="product.id", primary_key=True)
