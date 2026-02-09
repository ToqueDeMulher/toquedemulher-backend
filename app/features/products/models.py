from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, date

from sqlmodel import SQLModel, Field, Relationship

from app.core.db import UserInDB


# ======================================================
# TABELAS DE LIGACAO (N:N)
# ======================================================

class CategoryProductLink(SQLModel, table=True):
    category_id: int = Field(foreign_key="category.id", primary_key=True)
    product_id: UUID = Field(foreign_key="product.id", primary_key=True)


# ======================================================
# PRODUTO E RELACOES
# ======================================================

class Category(SQLModel, table=True):
    __tablename__ = "category"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    products: List["Product"] = Relationship(
        back_populates="categories",
        link_model=CategoryProductLink,
    )


class Supplier(SQLModel, table=True):
    __tablename__ = "supplier"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    contact: Optional[str] = None
    email: Optional[str] = None

    products: List["Product"] = Relationship(back_populates="supplier")


class Brand(SQLModel, table=True):
    __tablename__ = "brand"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    products: List["Product"] = Relationship(back_populates="brand")


class Description(SQLModel, table=True):
    __tablename__ = "description"

    id: Optional[int] = Field(default=None, primary_key=True)
    text: str
    usage_tips: Optional[str] = None
    ingredients: Optional[str] = None

    products: List["Product"] = Relationship(back_populates="description")


class Stock(SQLModel, table=True):
    __tablename__ = "stock"

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: UUID = Field(foreign_key="product.id")

    quantity: int
    expiry_date: Optional[date] = None
    last_update: datetime = Field(default_factory=datetime.utcnow)
    last_quantity: Optional[int] = None

    product: Optional["Product"] = Relationship(back_populates="stock_items")


class Product(SQLModel, table=True):
    __tablename__ = "product"

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

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    supplier_id: Optional[int] = Field(default=None, foreign_key="supplier.id")
    brand_id: Optional[int] = Field(default=None, foreign_key="brand.id")
    description_id: Optional[int] = Field(default=None, foreign_key="description.id")

    supplier: Optional[Supplier] = Relationship(back_populates="products")
    brand: Optional[Brand] = Relationship(back_populates="products")
    description: Optional[Description] = Relationship(back_populates="products")

    categories: List[Category] = Relationship(
        back_populates="products",
        link_model=CategoryProductLink,
    )
    stock_items: List[Stock] = Relationship(back_populates="product")
    images: List["ProductImage"] = Relationship(back_populates="product")
    reviews: List["ProductReview"] = Relationship(back_populates="product")
    cart_items: List["CartItem"] = Relationship(back_populates="product")
    order_items: List["OrderItem"] = Relationship(back_populates="product")


class ProductReview(SQLModel, table=True):
    __tablename__ = "product_review"

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: UUID = Field(foreign_key="product.id")
    user_id: UUID = Field(foreign_key="userindb.id")

    rating: int
    title: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    product: Optional[Product] = Relationship(back_populates="reviews")
    user: Optional[UserInDB] = Relationship(back_populates="reviews")


class ProductImage(SQLModel, table=True):
    __tablename__ = "product_image"

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: UUID = Field(foreign_key="product.id")

    url: str
    order: int = Field(default=1)
    alt_text: Optional[str] = None

    product: Optional[Product] = Relationship(back_populates="images")
