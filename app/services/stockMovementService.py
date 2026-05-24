from uuid import UUID
from typing import Optional
from sqlmodel import Session
from app.models.stockMovement import StockMovement, StockMovementType

def create_stock_movement(
    session: Session,
    product_id: UUID,
    stock_id: UUID,
    movement_type: StockMovementType,
    quantity: int,
    reason: Optional[str] = None,
    order_id: Optional[UUID] = None
) -> StockMovement:

    movement = StockMovement(
        product_id=product_id,
        stock_id=stock_id,
        movement_type=movement_type,
        quantity=quantity,
        reason=reason,
        order_id=order_id
    )

    session.add(movement)

    return movement