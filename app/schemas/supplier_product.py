from typing import Optional
from pydantic import BaseModel
from typing import List

class SupplierProductRequest(BaseModel):
    supplier_name: str
    supplier_price: float
    lead_time_days: Optional[int] = None


class SupplierAndProductRequest(BaseModel):   
    supplier: List[SupplierProductRequest]
    products_list: List[str]

