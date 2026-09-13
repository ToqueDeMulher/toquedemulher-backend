import stripe
from decimal import Decimal, ROUND_HALF_UP

from app.core.settings import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def _to_cents(value: Decimal | float | int) -> int:
    amount = Decimal(str(value)) * Decimal("100")
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def create_checkout_session(
    items,
    order_id,
    payer_email: str | None = None,
    idempotency_key: str | None = None,
):
    line_items = []

    for item in items:
        line_items.append(
            {
                "price_data": {
                    "currency": "brl",
                    "product_data": {
                        "name": item["name"],
                    },
                    "unit_amount": _to_cents(item["unit_price"]),
                },
                "quantity": item["quantity"],
            }
        )

    metadata = {
        "order_id": str(order_id),
    }
    if idempotency_key:
        metadata["idempotency_key"] = idempotency_key

    session_payload = {
        "mode": "payment",
        "line_items": line_items,
        "success_url": f"{settings.FRONTEND_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{settings.FRONTEND_FAILURE_URL}?order_id={order_id}",
        "metadata": metadata,
        "payment_intent_data": {
            "metadata": metadata,
        },
        "client_reference_id": str(order_id),
    }
    if payer_email:
        session_payload["customer_email"] = payer_email

    request_options = {}
    if idempotency_key:
        request_options["idempotency_key"] = idempotency_key

    checkout_session = stripe.checkout.Session.create(
        **session_payload,
        **request_options,
    )

    return checkout_session


def retrieve_checkout_session(session_id: str):
    return stripe.checkout.Session.retrieve(session_id)


def expire_checkout_session(session_id: str):
    return stripe.checkout.Session.expire(session_id)