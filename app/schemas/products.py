from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class ProductRequest(BaseModel):
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
    vegan: bool = False
    cruelty_free: bool = False
    hypoallergenic: bool = False


class ProductResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    price: float
    active: bool
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
    created_at: datetime
    updated_at: datetime
    supplier_id: Optional[int] = None
    brand_id: Optional[int] = None
    description_id: Optional[int] = None