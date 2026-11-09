from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class SupplierProductRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    supplier_name: str
    supplier_price: float = Field(ge=0)
    lead_time_days: Optional[int] = Field(default=None, ge=0)


class ProductSupplierItemRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    product_name: str
    supplier_price: float = Field(ge=0)
    lead_time_days: Optional[int] = Field(default=None, ge=0)


class SupplierAndProductRequest(BaseModel):
    supplier_name: str
    products_list: List[ProductSupplierItemRequest]

