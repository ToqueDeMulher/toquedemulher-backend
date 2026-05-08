from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from app.core.time import utc_now

class StockMovementType(str, Enum):
    IN = "IN"
    OUT = "OUT"
    ADJUSTMENT = "ADJUSTMENT"
    RETURN = "RETURN"


class StockMovement(SQLModel, table=True):
    __tablename__ = "stock_movement"

    id: UUID = Field(default_factory=uuid4, primary_key=True)

    product_id: UUID = Field(foreign_key="product.id", index=True)
    stock_id: UUID = Field(foreign_key="stock.id", index=True)

    movement_type: StockMovementType
    quantity: int

    reason: Optional[str] = None
    order_id: Optional[UUID] = None

    created_at: datetime = Field(default_factory=utc_now)