import uuid
import mercadopago
from app.core.settings import settings
from app.services.mercadopago_client import get_mp_sdk
from app.schemas.create_preference import CreatePreferenceRequest, CreatePreferenceResponse



def create_payment_preference(preference: CreatePreferenceRequest)-> CreatePreferenceResponse:
    sdk = get_mp_sdk()

    preference_data = {
        "items": preference.items,
        "payer": {
            "email": preference.payer_email
        },
        "external_reference": preference.order_id,
    }

    request_options = mercadopago.config.RequestOptions()
    request_options.custom_headers = {
        "x-idempotency-key": str(uuid.uuid4()) #evitar duplicidades
    }

    print("PREFERENCE DATA:", preference_data)

    result = sdk.preference().create(preference_data, request_options)

    print("RESULTADO COMPLETO MP:", result)

    response = result.get("response", {})
    print("RESPONSE MP:", response)

    preferenceResponde = CreatePreferenceResponse(
        preference_id = response.get("id"),
        init_point = response.get("init_point"),
        sandbox_init_point = response.get("sandbox_init_point"),
        raw = response,
    )

    return preferenceResponde