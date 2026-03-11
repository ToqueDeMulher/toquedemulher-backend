from typing import Optional
from uuid import UUID
from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship
from app.models.product import Product

class ProductImage(SQLModel, table=True):
    __tablename__ = "product_image"
    __table_args__ = (
        CheckConstraint('"order" >= 1', name="ck_product_image_order_positive"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: UUID = Field(foreign_key="product.id", index=True)

    url: str
    order: int = Field(default=1)
    alt_text: Optional[str] = None

    product: Optional[Product] = Relationship(back_populates="images")