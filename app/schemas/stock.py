from typing import Optional
from datetime import date
from pydantic import BaseModel, Field


class StockRequest(BaseModel):
    quantity: int = Field(ge=0)
    # string tipo "YYYY-MM-DD" ou null -> Pydantic converte pra date
    expiry_date: Optional[date] = None

    