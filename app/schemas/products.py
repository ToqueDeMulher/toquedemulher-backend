from pydantic import BaseModel, ConfigDict
from typing import Optional
from uuid import UUID
from app.schemas.supplier_product import SupplierProductRequest
from typing import List

class ProductRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slug: Optional[str] = None
    name: str
    price: float
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

    brand_id: Optional[int] = None
    description_id: Optional[int] = None
    supplier_products: Optional[List[SupplierProductRequest]] = []

class ProductResponse(BaseModel):
    id: UUID
    slug: str
    name: str
    price: float
