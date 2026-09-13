import logging
from uuid import UUID

import stripe
from fastapi import APIRouter, HTTPException, Request
from sqlmodel import select

from app.core.db import _SessionDep
from app.core.settings import settings
from app.core.time import utc_now
from app.models.payment import Payment, PaymentStatus
from app.services.paymentStockService import release_checkout_stock


logger = logging.getLogger(__name__)
router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY

_CHECKOUT_EVENTS = {
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "checkout.session.expired",
}
_SUPPORTED_EVENTS = _CHECKOUT_EVENTS | {"charge.refunded"}
_FINAL_FAILURE_STATUSES = {
    PaymentStatus.REJECTED.value,
    PaymentStatus.CANCELLED.value,
}


def _object_value(stripe_object, key: str, default=None):
    if hasattr(stripe_object, "get"):
        return stripe_object.get(key, default)
    return getattr(stripe_object, key, default)


def _metadata_order_id(data) -> UUID | None:
    metadata = _object_value(data, "metadata", {}) or {}
    raw_order_id = _object_value(metadata, "order_id")
    if not raw_order_id:
        return None

    try:
        return UUID(str(raw_order_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="order_id inválido no metadata",
        ) from exc


def _find_payment(event_type: str, data, session: _SessionDep) -> Payment | None:
    payment = None

    if event_type in _CHECKOUT_EVENTS:
        checkout_session_id = _object_value(data, "id")
        if checkout_session_id:
            payment = session.exec(
                select(Payment)
                .where(Payment.provider_session_id == checkout_session_id)
                .with_for_update()
            ).first()
    elif event_type == "charge.refunded":
        payment_intent_id = _object_value(data, "payment_intent")
        if payment_intent_id:
            payment = session.exec(
                select(Payment)
                .where(Payment.provider_payment_id == payment_intent_id)
                .with_for_update()
            ).first()

    if payment:
        return payment

    order_id = _metadata_order_id(data)
    if not order_id:
        return None

    return session.exec(
        select(Payment)
        .where(Payment.order_id == order_id)
        .with_for_update()
    ).first()


def _target_status(event_type: str, data) -> str:
    if event_type == "checkout.session.completed":
        payment_status = _object_value(data, "payment_status")
        if payment_status in {"paid", "no_payment_required"}:
            return PaymentStatus.APPROVED.value
        return PaymentStatus.PENDING.value
    if event_type == "checkout.session.async_payment_succeeded":
        return PaymentStatus.APPROVED.value
    if event_type == "checkout.session.async_payment_failed":
        return PaymentStatus.REJECTED.value
    if event_type == "checkout.session.expired":
        return PaymentStatus.CANCELLED.value
    return PaymentStatus.REFUNDED.value


def _can_transition(current_status: str, target_status: str) -> bool:
    if current_status == target_status:
        return False
    if current_status == PaymentStatus.REFUNDED.value:
        return False
    if current_status == PaymentStatus.APPROVED.value:
        return target_status == PaymentStatus.REFUNDED.value
    if current_status in _FINAL_FAILURE_STATUSES:
        return False
    return True


@router.post("/payments/webhook")
async def stripe_webhook(request: Request, session: _SessionDep):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Stripe-Signature ausente")
    if not settings.STRIPE_WEBHOOK_SECRET.strip():
        raise HTTPException(status_code=500, detail="Webhook Stripe não configurado")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Payload inválido") from exc
    except stripe.SignatureVerificationError as exc:
        raise HTTPException(
            status_code=400,
            detail="Assinatura do webhook inválida",
        ) from exc

    event_type = event["type"]
    if event_type not in _SUPPORTED_EVENTS:
        return {"status": "ignored", "event_type": event_type}

    data = event["data"]["object"]
    target_status = _target_status(event_type, data)

    try:
        with session.begin_nested():
            payment = _find_payment(event_type, data, session)
            if not payment:
                return {"status": "ignored", "reason": "payment não encontrado"}

            current_status = str(payment.status)
            if not _can_transition(current_status, target_status):
                return {
                    "status": "ok",
                    "payment_status": current_status,
                    "duplicate": current_status == target_status,
                }

            if target_status in _FINAL_FAILURE_STATUSES:
                release_checkout_stock(
                    session=session,
                    payment=payment,
                    reason=(
                        "Liberação de reserva: sessão Stripe expirada"
                        if target_status == PaymentStatus.CANCELLED.value
                        else "Liberação de reserva: pagamento Stripe recusado"
                    ),
                )

            provider_payment_id = _object_value(data, "payment_intent")
            if provider_payment_id:
                payment.provider_payment_id = str(provider_payment_id)

            payment.status = target_status
            payment.updated_at = utc_now()
            session.add(payment)

        session.commit()
        session.refresh(payment)
    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        logger.exception(
            "Erro ao processar webhook Stripe: event_type=%s",
            event_type,
        )
        raise HTTPException(
            status_code=500,
            detail="Erro ao processar webhook Stripe",
        ) from exc

    return {"status": "ok", "payment_status": payment.status}