from collections import defaultdict
from uuid import UUID

from sqlmodel import Session, select

from app.core.time import utc_now
from app.models.payment import Payment
from app.models.paymentItem import PaymentItem
from app.models.stock import Stock
from app.models.stockMovement import StockMovement, StockMovementType
from app.services.stockMovementService import create_stock_movement


def release_checkout_stock(
    session: Session,
    payment: Payment,
    reason: str,
) -> int:
    """Libera uma reserva de checkout uma única vez e registra RETURN."""

    quantities_by_product: dict[UUID, int] = defaultdict(int)
    items = session.exec(
        select(PaymentItem).where(PaymentItem.payment_id == payment.id)
    ).all()

    for item in items:
        quantities_by_product[item.product_id] += item.quantity

    released_quantity = 0
    for product_id in sorted(quantities_by_product, key=str):
        stock = session.exec(
            select(Stock)
            .where(Stock.product_id == product_id)
            .with_for_update()
        ).first()
        if not stock:
            raise RuntimeError(
                f"Estoque não encontrado ao liberar a reserva do produto {product_id}"
            )

        existing_return = session.exec(
            select(StockMovement).where(
                StockMovement.order_id == payment.order_id,
                StockMovement.product_id == product_id,
                StockMovement.movement_type == StockMovementType.RETURN,
            )
        ).first()
        if existing_return:
            continue

        quantity = quantities_by_product[product_id]
        stock.total_quantity += quantity
        stock.updated_at = utc_now()
        session.add(stock)
        create_stock_movement(
            session=session,
            product_id=product_id,
            stock_id=stock.id,
            movement_type=StockMovementType.RETURN,
            quantity=quantity,
            reason=reason,
            order_id=payment.order_id,
        )
        released_quantity += quantity

    return released_quantity