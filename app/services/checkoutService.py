import stripe
from uuid import UUID
from app.core.settings import settings
import time

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(payload, order_id):
    line_items = []

    for item in payload.items:
        line_items.append(
            {
                "price_data": {
                    "currency": "brl",
                    "product_data": {
                        "name": item.name,
                    },
                    "unit_amount": int(float(item.unit_price) * 100),
                },
                "quantity": item.quantity,
            }
        )

    checkout_session = stripe.checkout.Session.create(
        ui_mode="embedded",
        mode="payment",
        line_items=line_items,
        return_url="http://localhost:3000/checkout/retorno?session_id={CHECKOUT_SESSION_ID}",
        metadata={
            "order_id": str(order_id)
        }
    )

    return checkout_session