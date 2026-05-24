import mercadopago
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.core.config import settings
from app.models.payment import PaymentMethod, PaymentProvider
import logging

logger = logging.getLogger(__name__)


def get_mercadopago_sdk() -> mercadopago.SDK:
    """Retorna instância configurada do SDK do Mercado Pago."""
    return mercadopago.SDK(settings.MERCADOPAGO_ACCESS_TOKEN)


def create_pix_payment(
    order_number: str,
    amount: float,
    payer_email: str,
    payer_name: str,
    payer_cpf: str,
) -> Dict[str, Any]:
    """
    Cria um pagamento via PIX no Mercado Pago.
    Retorna os dados do QR Code e informações do pagamento.
    """
    sdk = get_mercadopago_sdk()

    payment_data = {
        "transaction_amount": round(amount, 2),
        "description": f"Pedido #{order_number} - O Toque de Mulher",
        "payment_method_id": "pix",
        "payer": {
            "email": payer_email,
            "first_name": payer_name.split()[0],
            "last_name": " ".join(payer_name.split()[1:]) if len(payer_name.split()) > 1 else "",
            "identification": {
                "type": "CPF",
                "number": payer_cpf.replace(".", "").replace("-", ""),
            },
        },
        "date_of_expiration": (datetime.utcnow() + timedelta(hours=24)).strftime(
            "%Y-%m-%dT%H:%M:%S.000-03:00"
        ),
        "external_reference": order_number,
        "notification_url": f"{settings.FRONTEND_URL}/api/v1/payments/webhook/mercadopago",
    }

    try:
        result = sdk.payment().create(payment_data)
        response = result["response"]

        if result["status"] == 201:
            return {
                "success": True,
                "provider_payment_id": str(response["id"]),
                "status": response["status"],
                "pix_qr_code": response["point_of_interaction"]["transaction_data"]["qr_code"],
                "pix_qr_code_base64": response["point_of_interaction"]["transaction_data"]["qr_code_base64"],
                "pix_expiration": datetime.utcnow() + timedelta(hours=24),
                "raw_response": response,
            }
        else:
            logger.error(f"Erro ao criar pagamento PIX: {response}")
            return {"success": False, "error": str(response)}
    except Exception as e:
        logger.error(f"Exceção ao criar pagamento PIX: {e}")
        return {"success": False, "error": str(e)}


def create_boleto_payment(
    order_number: str,
    amount: float,
    payer_email: str,
    payer_name: str,
    payer_cpf: str,
    payer_address: Dict[str, str],
) -> Dict[str, Any]:
    """Cria um pagamento via Boleto Bancário no Mercado Pago."""
    sdk = get_mercadopago_sdk()

    payment_data = {
        "transaction_amount": round(amount, 2),
        "description": f"Pedido #{order_number} - O Toque de Mulher",
        "payment_method_id": "bolbradesco",
        "payer": {
            "email": payer_email,
            "first_name": payer_name.split()[0],
            "last_name": " ".join(payer_name.split()[1:]) if len(payer_name.split()) > 1 else "",
            "identification": {
                "type": "CPF",
                "number": payer_cpf.replace(".", "").replace("-", ""),
            },
            "address": {
                "zip_code": payer_address.get("zip_code", "").replace("-", ""),
                "street_name": payer_address.get("street", ""),
                "street_number": payer_address.get("number", ""),
                "neighborhood": payer_address.get("neighborhood", ""),
                "city": payer_address.get("city", ""),
                "federal_unit": payer_address.get("state", ""),
            },
        },
        "external_reference": order_number,
        "notification_url": f"{settings.FRONTEND_URL}/api/v1/payments/webhook/mercadopago",
    }

    try:
        result = sdk.payment().create(payment_data)
        response = result["response"]

        if result["status"] == 201:
            return {
                "success": True,
                "provider_payment_id": str(response["id"]),
                "status": response["status"],
                "boleto_url": response.get("transaction_details", {}).get("external_resource_url"),
                "boleto_barcode": response.get("barcode", {}).get("content"),
                "boleto_expiration": datetime.utcnow() + timedelta(days=3),
                "raw_response": response,
            }
        else:
            logger.error(f"Erro ao criar boleto: {response}")
            return {"success": False, "error": str(response)}
    except Exception as e:
        logger.error(f"Exceção ao criar boleto: {e}")
        return {"success": False, "error": str(e)}


def create_credit_card_payment(
    order_number: str,
    amount: float,
    payer_email: str,
    payer_name: str,
    payer_cpf: str,
    card_token: str,
    installments: int = 1,
) -> Dict[str, Any]:
    """Cria um pagamento via Cartão de Crédito no Mercado Pago."""
    sdk = get_mercadopago_sdk()

    payment_data = {
        "transaction_amount": round(amount, 2),
        "token": card_token,
        "description": f"Pedido #{order_number} - O Toque de Mulher",
        "installments": installments,
        "payer": {
            "email": payer_email,
            "identification": {
                "type": "CPF",
                "number": payer_cpf.replace(".", "").replace("-", ""),
            },
        },
        "external_reference": order_number,
        "notification_url": f"{settings.FRONTEND_URL}/api/v1/payments/webhook/mercadopago",
    }

    try:
        result = sdk.payment().create(payment_data)
        response = result["response"]

        if result["status"] == 201:
            return {
                "success": True,
                "provider_payment_id": str(response["id"]),
                "status": response["status"],
                "raw_response": response,
            }
        else:
            logger.error(f"Erro ao criar pagamento com cartão: {response}")
            return {"success": False, "error": str(response)}
    except Exception as e:
        logger.error(f"Exceção ao criar pagamento com cartão: {e}")
        return {"success": False, "error": str(e)}


def get_payment_status(provider_payment_id: str) -> Optional[str]:
    """Consulta o status de um pagamento no Mercado Pago."""
    sdk = get_mercadopago_sdk()
    try:
        result = sdk.payment().get(provider_payment_id)
        if result["status"] == 200:
            return result["response"]["status"]
        return None
    except Exception as e:
        logger.error(f"Erro ao consultar pagamento {provider_payment_id}: {e}")
        return None
