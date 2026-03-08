from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.models.payment import Payment, PaymentStatus
from app.models.order import Order, OrderStatus, OrderTracking
from app.services import payment_service
import logging

router = APIRouter(prefix="/payments", tags=["Pagamentos"])
logger = logging.getLogger(__name__)


@router.post("/webhook/mercadopago")
async def mercadopago_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook para receber notificações de pagamento do Mercado Pago.
    O Mercado Pago envia notificações quando o status de um pagamento muda.
    """
    try:
        data = await request.json()
        logger.info(f"Webhook Mercado Pago recebido: {data}")

        # Processar apenas notificações de pagamento
        if data.get("type") != "payment":
            return {"status": "ignored"}

        provider_payment_id = str(data.get("data", {}).get("id"))
        if not provider_payment_id:
            return {"status": "ignored"}

        # Buscar pagamento no banco
        payment = db.query(Payment).filter(
            Payment.provider_payment_id == provider_payment_id
        ).first()
        if not payment:
            logger.warning(f"Pagamento não encontrado: {provider_payment_id}")
            return {"status": "not_found"}

        # Consultar status atualizado no Mercado Pago
        mp_status = payment_service.get_payment_status(provider_payment_id)
        if not mp_status:
            return {"status": "error"}

        # Mapear status do Mercado Pago para o nosso sistema
        status_map = {
            "approved": PaymentStatus.approved,
            "rejected": PaymentStatus.rejected,
            "cancelled": PaymentStatus.cancelled,
            "refunded": PaymentStatus.refunded,
            "in_process": PaymentStatus.in_process,
            "pending": PaymentStatus.pending,
        }

        new_payment_status = status_map.get(mp_status, PaymentStatus.pending)
        payment.status = new_payment_status

        # Atualizar status do pedido
        order = payment.order
        if new_payment_status == PaymentStatus.approved:
            order.status = OrderStatus.payment_confirmed
            tracking = OrderTracking(
                order_id=order.id,
                status=OrderStatus.payment_confirmed,
                description="Pagamento confirmado pelo Mercado Pago.",
            )
            db.add(tracking)
        elif new_payment_status in (PaymentStatus.rejected, PaymentStatus.cancelled):
            order.status = OrderStatus.cancelled
            tracking = OrderTracking(
                order_id=order.id,
                status=OrderStatus.cancelled,
                description=f"Pagamento {mp_status}.",
            )
            db.add(tracking)

        db.commit()
        return {"status": "processed"}

    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}")
        return {"status": "error", "detail": str(e)}
