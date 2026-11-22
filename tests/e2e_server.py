"""Local-only application for browser integration tests with simulated providers."""

import base64
import copy
import hmac
import os
import tempfile
from datetime import timedelta
from uuid import UUID

os.environ.update(
    {
        "DATABASE_URL": "sqlite:///"
        + os.path.join(tempfile.mkdtemp(prefix="tdm-e2e-"), "fixture.sqlite"),
        "SECRET_KEY": "local-browser-fixture-key-32-characters",
        "CREATE_TABLES_ON_STARTUP": "false",
        "EMAIL_CONFIRMATION_REQUIRED": "false",
        "SMTP_USER": "",
        "SMTP_PASSWORD": "",
        "GOOGLE_CLIENT_ID": "",
        "VITE_GOOGLE_CLIENT_ID": "",
        "ABACATEPAY_API_KEY": "dummy-local-provider",
        "ABACATEPAY_WEBHOOK_SECRET": "dummy-local-webhook-secret-32-characters",
        "ABACATEPAY_DEV_MODE": "true",
        "ABACATEPAY_CARD_ENABLED": "true",
        "PAYMENT_PROVIDER": "abacatepay",
        "CORS_ORIGINS": "http://127.0.0.1:4174",
        "MELHOR_ENVIO_ENVIRONMENT": "sandbox",
        "MELHOR_ENVIO_FREE_SHIPPING_THRESHOLD": "0",
    }
)
import json
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session, select

from app.api.v1.endpoints.abacatepay_webhook import SIGNING_KEY
from app.core.db import Database
from app.core.settings import settings
from app.main import app
from app.models.payment import Payment
from app.models.product import Product
from app.models.stock import Stock
from app.services import abacatepay, melhor_envio

PRODUCT_ID = UUID("a1000000-0000-4000-8000-000000000001")
SENDER = {
    "name": "Loja Fixture",
    "email": "loja@example.com",
    "phone": "11999999999",
    "address": "Rua Fixture",
    "number": "1",
    "district": "Centro",
    "city": "São Paulo",
    "state_abbr": "SP",
    "postal_code": "01001000",
    "company_document": "12345678000195",
    "state_register": "ISENTO",
}
settings.MELHOR_ENVIO_SENDER = json.dumps(SENDER)
settings.MELHOR_ENVIO_USER_AGENT = "TDM QA (fixture@example.com)"
Database.create_db_and_tables()
with Session(Database.engine) as session:
    session.add(
        Product(
            id=PRODUCT_ID,
            name="Batom integração",
            slug="batom-integracao",
            price=49.9,
            shipping_width=11,
            shipping_height=2,
            shipping_length=16,
            shipping_weight=0.1,
        )
    )
    session.commit()
    session.add(Stock(product_id=PRODUCT_ID, total_quantity=10))
    session.commit()

charges = {}
official = json.loads(
    (Path(__file__).parent / "fixtures/melhor_envio_calculate.json").read_text()
)


def freight(session, method, path, **kwargs):
    if method != "POST" or not path.endswith("/calculate"):
        raise HTTPException(503, "Operação externa indisponível no teste")
    response = copy.deepcopy(official)
    for service in response:
        if not service.get("error"):
            for package in service["packages"]:
                package["products"] = [{"id": str(PRODUCT_ID), "quantity": 1}]
    return response


def gateway(method, path, *, params=None, payload=None, **kwargs):
    if method == "POST" and path == "transparents/create":
        reference = payload["data"]["externalId"]
        charge = {
            "id": "pix_char_" + reference,
            "amount": payload["data"]["amount"],
            "status": "PENDING",
            "devMode": True,
            "metadata": {"order_id": reference},
            "brCode": "000201-local-integration-fixture",
            "brCodeBase64": "data:image/png;base64,aGVsbG8=",
            "expiresAt": "2030-01-01T12:00:00Z",
        }
        charges[charge["id"]] = charge
        return charge
    if method == "GET" and path == "transparents/list":
        return [
            charge
            for charge in charges.values()
            if charge["id"] == params.get("id")
            or charge["metadata"]["order_id"] == params.get("externalId")
        ]
    raise HTTPException(503, "Operação externa indisponível no teste")


melhor_envio.request = freight
abacatepay._request = gateway
abacatepay.CHECK_INTERVAL = timedelta(0)


@app.post("/__fixtures/pay/{order_id}")
def settle_fixture(order_id: UUID):
    with Session(Database.engine) as session:
        payment = session.exec(
            select(Payment).where(Payment.order_id == order_id)
        ).one()
        charges[payment.provider_session_id]["status"] = "PAID"
        provider_id = payment.provider_session_id
    payload = json.dumps(
        {
            "id": "log_" + str(order_id),
            "event": "transparent.completed",
            "apiVersion": 2,
            "devMode": True,
            "data": {"transparent": {"id": provider_id}},
        }
    )
    return {
        "payload": payload,
        "signature": base64.b64encode(
            hmac.digest(SIGNING_KEY, payload.encode(), "sha256")
        ).decode(),
    }


@app.get("/__fixtures/orders/{order_id}")
def fixture_state(order_id: UUID):
    with Session(Database.engine) as session:
        payment = session.exec(
            select(Payment).where(Payment.order_id == order_id)
        ).one()
        stock = session.exec(select(Stock).where(Stock.product_id == PRODUCT_ID)).one()
        return {
            "status": payment.status,
            "stock": stock.total_quantity,
            "amount": str(payment.amount),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8008, access_log=False)
