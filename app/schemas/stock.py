from typing import Optional
from datetime import date
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class stockItemRequest(BaseModel):
    product_name: str
    quantity: int = Field(gt=0)
    unit_cost: float = Field(gt=0)
    expiry_date: Optional[date] = None

class StockRequest(BaseModel):
    supplier_name: str
    items: List[stockItemRequest] = Field(min_length=1)

class GetStock(BaseModel):
    name: str
    quantity: int
    last_update: datetime