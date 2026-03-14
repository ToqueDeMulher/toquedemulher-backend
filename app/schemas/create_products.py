from typing import List
from uuid import UUID
from pydantic import BaseModel, Field

from app.schemas.products import ProductRequest
from app.schemas.suppliers import SupplierRequest
from app.schemas.brands import BrandRequest
from app.schemas.descriptions import DescriptionRequest
from app.schemas.categories import CategoryRequest
from app.schemas.stock import StockRequest
from app.schemas.product_images import ProductImageRequest


class CreateProductRequest(BaseModel):
    product: ProductRequest
    supplier: SupplierRequest
    brand: BrandRequest
    description: DescriptionRequest
    categories: List[CategoryRequest] = Field(default_factory=list)
    stock: StockRequest
    images: List[ProductImageRequest] = Field(default_factory=list)


class CreateProductResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    supplier_id: int | None = None
    brand_id: int | None = None
    description_id: int | None = None