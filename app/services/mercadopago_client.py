import mercadopago
from app.core.settings import settings

def get_mp_sdk():
    print("TOKEN:", settings.MERCADO_PAGO_ACCESS_TOKEN[:20], "...")
    return mercadopago.SDK(settings.MERCADO_PAGO_ACCESS_TOKEN)