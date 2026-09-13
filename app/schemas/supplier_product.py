from typing import Optional, List
from pydantic import BaseModel, Field


class SupplierProductRequest(BaseModel):
    supplier_name: str
    supplier_price: float = Field(ge=0)
    lead_time_days: Optional[int] = Field(default=None, ge=0)


class ProductSupplierItemRequest(BaseModel):
    product_name: str
    supplier_price: float = Field(ge=0)
    lead_time_days: Optional[int] = Field(default=None, ge=0)


class SupplierAndProductRequest(BaseModel):
    supplier_name: str
    products_list: List[ProductSupplierItemRequest]

