from uuid import uuid4
import mercadopago
from app.core.settings import settings
from app.schemas.create_preference import (
    CreatePreferenceResponse,CreatePreferenceRequestWithOrder
)
from app.services.mercadopago_client import get_mp_sdk


def create_payment_preference(preference: CreatePreferenceRequestWithOrder) -> CreatePreferenceResponse:
    sdk = get_mp_sdk()

    preference_data = {
        "items": [
            {
                "id": item.id,
                "title": item.title,
                "quantity": item.quantity,
                "currency_id": "BRL",
                "unit_price": item.unit_price,
            }
            for item in preference.items
        ],
        "payer": {
            "email": preference.payer_email
        },
        "external_reference": preference.order_id,
        "notification_url": settings.MERCADO_PAGO_WEBHOOK_URL,
    }

    request_options = mercadopago.config.RequestOptions()
    request_options.custom_headers = {
        "x-idempotency-key": str(uuid4())
    }

    result = sdk.preference().create(preference_data, request_options)
    response = result.get("response", {})

    return CreatePreferenceResponse(
        preference_id=response.get("id"),
        init_point=response.get("init_point"),
        sandbox_init_point=response.get("sandbox_init_point"),
        raw=response,
    )