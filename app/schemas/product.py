from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.models.product import ProductStatus


class CategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_id: Optional[int] = None
    is_active: bool = True


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_id: Optional[int] = None
    is_active: Optional[bool] = None


class CategoryOut(CategoryBase):
    id: int
    slug: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProductImageOut(BaseModel):
    id: int
    url: str
    alt_text: Optional[str] = None
    is_primary: bool
    sort_order: int

    class Config:
        from_attributes = True


class ProductVariantBase(BaseModel):
    name: str
    sku: Optional[str] = None
    price: Optional[float] = None
    stock_quantity: int = 0
    attributes: Optional[Dict[str, Any]] = None
    is_active: bool = True


class ProductVariantCreate(ProductVariantBase):
    pass


class ProductVariantUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[float] = None
    stock_quantity: Optional[int] = None
    attributes: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ProductVariantOut(ProductVariantBase):
    id: int
    product_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    short_description: Optional[str] = None
    sku: Optional[str] = None
    brand: Optional[str] = None
    price: float
    compare_at_price: Optional[float] = None
    cost_price: Optional[float] = None
    stock_quantity: int = 0
    weight: Optional[float] = None
    status: ProductStatus = ProductStatus.active
    is_featured: bool = False
    tags: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    category_id: Optional[int] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    short_description: Optional[str] = None
    sku: Optional[str] = None
    brand: Optional[str] = None
    price: Optional[float] = None
    compare_at_price: Optional[float] = None
    cost_price: Optional[float] = None
    stock_quantity: Optional[int] = None
    weight: Optional[float] = None
    status: Optional[ProductStatus] = None
    is_featured: Optional[bool] = None
    tags: Optional[List[str]] = None
    attributes: Optional[Dict[str, Any]] = None
    category_id: Optional[int] = None


class ProductOut(ProductBase):
    id: int
    slug: str
    average_rating: float
    review_count: int
    images: List[ProductImageOut] = []
    variants: List[ProductVariantOut] = []
    category: Optional[CategoryOut] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProductListOut(BaseModel):
    """Schema simplificado para listagens."""
    id: int
    name: str
    slug: str
    brand: Optional[str] = None
    price: float
    compare_at_price: Optional[float] = None
    stock_quantity: int
    status: ProductStatus
    is_featured: bool
    average_rating: float
    review_count: int
    primary_image: Optional[str] = None
    category: Optional[CategoryOut] = None

    class Config:
        from_attributes = True


class PaginatedProducts(BaseModel):
    items: List[ProductListOut]
    total: int
    page: int
    page_size: int
    total_pages: int
