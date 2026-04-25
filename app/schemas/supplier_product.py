from typing import Optional
from pydantic import BaseModel

class SupplierProductRequest(BaseModel):
    supplier_name: str
    supplier_price: float
    lead_time_days: Optional[int] = None