import stripe
from uuid import UUID
from app.core.settings import settings

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_checkout_session(payload, order_id: UUID):

    session = stripe.checkout.Session.create(

        payment_method_types=["card"],

        line_items=[
            {
                "price_data": {
                    "currency": "brl",
                    "product_data": {
                        "name": item.title,
                    },
                    "unit_amount": int(item.unit_price * 100),
                },
                "quantity": item.quantity,
            }
            for item in payload.items
        ],

        mode="payment",

        customer_email=payload.payer_email,

        metadata={
            "order_id": str(order_id)
        },

        success_url="http://localhost:3000/success",
        cancel_url="http://localhost:3000/cancel",
    )

    return session