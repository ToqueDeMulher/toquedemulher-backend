from typing import Optional, List
from pydantic import BaseModel


class SupplierProductRequest(BaseModel):
    supplier_name: str
    supplier_price: float
    lead_time_days: Optional[int] = None


class ProductSupplierItemRequest(BaseModel):
    product_name: str
    supplier_price: float
    lead_time_days: Optional[int] = None


class SupplierAndProductRequest(BaseModel):
    supplier_name: str
    products_list: List[ProductSupplierItemRequest]

