from typing import List, Optional
from datetime import date

from pydantic import BaseModel, EmailStr, Field


class ProductPayload(BaseModel):
    name: str
    price: float = Field(ge=0)
    active: bool = True
    volume: Optional[str] = None
    target_audience: Optional[str] = None
    product_type: Optional[str] = None
    skin_type: Optional[str] = None
    hair_type: Optional[str] = None
    color: Optional[str] = None
    fragrance: Optional[str] = None
    spf: Optional[int] = None
    vegan: bool
    cruelty_free: bool
    hypoallergenic: bool


class SupplierPayload(BaseModel):
    name: str
    contact: Optional[str] = None
    email: Optional[EmailStr] = None


class BrandPayload(BaseModel):
    name: str


class DescriptionPayload(BaseModel):
    text: str
    usage_tips: Optional[str] = None
    ingredients: Optional[str] = None


class CategoryPayload(BaseModel):
    name: str


class StockPayload(BaseModel):
    quantity: int = Field(ge=0)
    # string tipo "YYYY-MM-DD" ou null -> Pydantic converte pra date
    expiry_date: Optional[date] = None


class ProductImagePayload(BaseModel):
    url: str
    order: int = Field(ge=1)
    alt_text: Optional[str] = None


class ProductImageResponse(BaseModel):
    id: int
    url: str
    order: int = Field(ge=1)
    alt_text: Optional[str] = None


class CreateProductPayload(BaseModel):
    product: ProductPayload
    supplier: SupplierPayload
    brand: BrandPayload
    description: DescriptionPayload
    categories: List[CategoryPayload] = Field(default_factory=list)
    stock: StockPayload
    images: List[ProductImagePayload] = Field(default_factory=list)
