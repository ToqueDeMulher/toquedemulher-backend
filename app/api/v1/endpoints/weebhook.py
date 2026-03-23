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

    event = stripe.Webhook.construct_event(
        payload,
        sig_header,
        settings.STRIPE_WEBHOOK_SECRET
    )

    event_type = event["type"]

    EVENT_STATUS_MAP = {
    "checkout.session.completed": PaymentStatus.APPROVED,
    "payment_intent.payment_failed": PaymentStatus.REJECTED,
    "charge.refunded": PaymentStatus.REFUNDED
}
    if event_type in EVENT_STATUS_MAP:

        data = event["data"]["object"]

        order_id = data["metadata"]["order_id"]

        status = EVENT_STATUS_MAP[event_type]

        payment_intent = data.get("payment_intent")

        payment = session.exec(
            select(Payment).where(Payment.order_id == order_id)
        ).first()

        if payment and payment.status != status:

            payment.status = status
            payment.provider_payment_id = payment_intent

            session.add(payment)
            session.commit()

        return {"status": "ok"}