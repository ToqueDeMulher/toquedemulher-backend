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
async def stripe_webhook(request: Request):

    payload = await request.body()

    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("Erro webhook:", e)
        raise HTTPException(status_code=400)

    print("Evento recebido:", event["type"])

    if event["type"] == "checkout.session.completed":

        session_data = event["data"]["object"]

        metadata = session_data.get("metadata", {})

        order_id = metadata.get("order_id")

        payment_intent = session_data.get("payment_intent")

        print("Pagamento aprovado")
        print("Order ID:", order_id)
        print("Payment Intent:", payment_intent)

    return {"status": "ok"}