from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now
from app.models.supplier import Supplier
from app.models.brand import Brand
from app.models.description import Description
from app.models.category import Category
from app.models.categoryProductLink import CategoryProductLink
from app.models.stock import Stock


class Product(SQLModel, table=True):
    __tablename__ = "product"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_product_price_non_negative"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    slug: str = Field(index=True, unique=True)
    name: str
    price: float
    active: bool = Field(default=True)
    volume: Optional[str] = None

    target_audience: Optional[str] = None
    product_type: Optional[str] = None
    skin_type: Optional[str] = None
    hair_type: Optional[str] = None
    color: Optional[str] = None
    fragrance: Optional[str] = None
    spf: Optional[int] = None
    vegan: bool = Field(default=False)
    cruelty_free: bool = Field(default=False)
    hypoallergenic: bool = Field(default=False)

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id", index=True)
    brand_id: Optional[int] = Field(default=None, foreign_key="brand.id", index=True)
    description_id: Optional[int] = Field(default=None, foreign_key="description.id", index=True)

    supplier: Optional[Supplier] = Relationship(back_populates="products")
    brand: Optional[Brand] = Relationship(back_populates="products")
    description: Optional[Description] = Relationship(back_populates="products")

    categories: List[Category] = Relationship(
        back_populates="products",
        link_model=CategoryProductLink,
    )
    stock_items: List[Stock] = Relationship(back_populates="product")       #type: ignore
    images: List["ProductImage"] = Relationship(back_populates="product")   #type: ignore
    reviews: List["ProductReview"] = Relationship(back_populates="product") #type: ignore
    cart_items: List["CartItem"] = Relationship(back_populates="product")   #type: ignore
    order_items: List["OrderItem"] = Relationship(back_populates="product") #type: ignore