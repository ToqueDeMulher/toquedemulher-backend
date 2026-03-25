import stripe
from fastapi import APIRouter, Request, HTTPException
from uuid import UUID
from sqlmodel import select

from app.core.settings import settings
from app.core.db import _SessionDep
from app.models.payment import Payment, PaymentStatus


router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/payments/webhook")
async def stripe_webhook(request: Request, session: _SessionDep):

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Stripe-Signature ausente")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Assinatura do webhook inválida")

    event_type = event["type"] 
    data = event["data"]["object"]

    EVENT_STATUS_MAP = {
        "checkout.session.completed": PaymentStatus.APPROVED.value,
        "payment_intent.payment_failed": PaymentStatus.REJECTED.value,
        "checkout.session.expired": PaymentStatus.CANCELLED.value,
        "charge.refunded": PaymentStatus.REFUNDED.value,
    }

    if event_type not in EVENT_STATUS_MAP:
        return {"status": "ignored", "event_type": event_type}

    status = EVENT_STATUS_MAP[event_type]

    order_id_raw = data.get("metadata", {}).get("order_id")
    if not order_id_raw:
        return {"status": "ignored", "reason": "order_id não encontrado no metadata"}

    try:
        order_id = UUID(order_id_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="order_id inválido no metadata")

    provider_payment_id = None

    if event_type in (
    "checkout.session.completed",
    "checkout.session.expired",
    "charge.refunded"
    ):
        provider_payment_id = data.get("payment_intent")
    elif event_type == "payment_intent.payment_failed":
        provider_payment_id = data.get("id")

    payment = session.exec(
        select(Payment).where(Payment.order_id == order_id)
    ).first()

    if not payment:
        return {"status": "ignored", "reason": "payment não encontrado"}

    if payment.status != status:
        payment.status = status
        payment.provider_payment_id = provider_payment_id
        session.add(payment)
        session.commit()
        session.refresh(payment)

    return {"status": "ok"}