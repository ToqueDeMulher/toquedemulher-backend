"""Integration tests use official response examples and isolated SQLite storage."""

import copy
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4
import httpx
import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from tests.test_auth import (
    client,
    engine,
    clean_db,
    create_logged_user,
    create_admin_token,
)
from app.core.settings import settings
from app.core.time import utc_now
from app.models.address import Address
from app.models.payment import Payment
from app.models.paymentItem import PaymentItem
from app.models.product import Product
from app.models.shipping import ShippingConnection, ShippingQuote, Shipment
from app.models.stock import Stock
from app.services import melhor_envio as me, brasil_api, shipment_service as operations

OFFICIAL = json.loads(
    (Path(__file__).parent / "fixtures/melhor_envio_calculate.json").read_text()
)
SENDER = {
    "name": "Loja",
    "email": "loja@example.com",
    "phone": "11999999999",
    "address": "Rua Loja",
    "number": "1",
    "district": "Centro",
    "city": "São Paulo",
    "state_abbr": "SP",
    "postal_code": "01001000",
    "company_document": "12345678000195",
    "state_register": "ISENTO",
}


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setattr(settings, "MELHOR_ENVIO_ENVIRONMENT", "sandbox")
    monkeypatch.setattr(settings, "MELHOR_ENVIO_SENDER", json.dumps(SENDER))
    monkeypatch.setattr(
        settings, "MELHOR_ENVIO_USER_AGENT", "Toque de Mulher (dev@example.com)"
    )
    monkeypatch.setattr(settings, "MELHOR_ENVIO_FREE_SHIPPING_THRESHOLD", 150)
    monkeypatch.setattr(settings, "SMTP_USER", "")
    monkeypatch.setattr(settings, "EMAIL_CONFIRMATION_REQUIRED", False)
    brasil_api._requests.clear()
    brasil_api._cache.clear()


def setup_product(price=49.9):
    with Session(engine) as session:
        product = Product(
            name="Batom Real",
            slug="batom-real",
            price=price,
            shipping_width=11,
            shipping_height=2,
            shipping_length=16,
            shipping_weight=0.1,
        )
        session.add(product)
        session.flush()
        session.add(Stock(product_id=product.id, total_quantity=20))
        session.commit()
        return str(product.id)


def fake_calculate(monkeypatch, product_id, quantity=1):
    data = copy.deepcopy(OFFICIAL)
    for service in data:
        if not service.get("error"):
            for package in service["packages"]:
                package["products"] = [{"id": product_id, "quantity": quantity}]
    calls = []

    def request(session, method, path, **kwargs):
        calls.append((method, path, kwargs))
        return data

    monkeypatch.setattr(me, "request", request)
    return data, calls


def make_quote(monkeypatch, product_id, quantity=1, postal_code="70000000"):
    fake_calculate(monkeypatch, product_id, quantity)
    response = client.post(
        "/api/v1/shipping/quotes",
        json={
            "postal_code": postal_code,
            "items": [{"id": product_id, "name": "Batom Real", "quantity": quantity}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def checkout(monkeypatch, product_id, quote, service_id=3):
    token = create_logged_user()
    headers = {"Authorization": f"Bearer {token}"}
    user = client.get("/api/v1/user/me", headers=headers).json()
    with Session(engine) as session:
        address = Address(
            user_id=UUID(user["id"]),
            cep=quote["postal_code"],
            street="Rua A",
            number="10",
            neighborhood="Centro",
            city="Brasília",
            state="DF",
        )
        session.add(address)
        session.commit()
        address_id = str(address.id)
    captured = {}

    def fake_stripe(items, order_id, **kwargs):
        captured.update(kwargs)
        return {"id": "cs_shipping_test", "url": "https://checkout.stripe.com/test"}

    monkeypatch.setattr(
        "app.api.v1.endpoints.stripeCheckout.create_checkout_session", fake_stripe
    )
    payload = {
        "address_id": address_id,
        "idempotency_key": str(uuid4()),
        "shipping": {
            "quote_id": quote["id"],
            "service_id": service_id,
            "recipient_name": "Maria Silva",
            "recipient_email": "maria@example.com",
            "recipient_phone": "11999999999",
            "recipient_document": "52998224725",
        },
        "items": [
            {
                "id": product_id,
                "name": "Batom Real",
                "unit_price": 1,
                "quantity": 1,
                "product_url": "/produto/1",
            }
        ],
    }
    return payload, headers, captured


def test_quote_uses_real_dimensions_prices_and_custom_fields(monkeypatch):
    product_id = setup_product()
    data, calls = fake_calculate(monkeypatch, product_id)
    data[0]["custom_price"] = "12.34"
    data[0]["custom_delivery_time"] = 7
    data[0]["custom_delivery_range"] = {"min": 6, "max": 7}
    result = client.post(
        "/api/v1/shipping/quotes",
        json={
            "postal_code": "70000000",
            "items": [
                {
                    "id": product_id,
                    "name": "Batom Real",
                    "quantity": 1,
                    "unit_price": 0.01,
                }
            ],
        },
    ).json()
    assert result["services"][0]["price"] == 12.34
    assert result["services"][0]["delivery_max"] == 7
    assert result["subtotal"] == 49.9
    assert result["expires_at"].endswith(("Z", "+00:00"))
    product = calls[0][2]["body"]["products"][0]
    assert product["weight"] == 0.1 and product["insurance_value"] == 49.9
    assert "packages" not in result["services"][0]


def test_free_shipping_only_sponsors_cheapest_option(monkeypatch):
    product_id = setup_product(200)
    quote = make_quote(monkeypatch, product_id)
    assert quote["services"][0]["price"] == 0
    assert all(service["price"] > 0 for service in quote["services"][1:])


def test_missing_dimensions_blocks_quote_without_provider_call(monkeypatch):
    product_id = setup_product()
    with Session(engine) as session:
        product = session.get(Product, UUID(product_id))
        product.shipping_weight = None
        session.add(product)
        session.commit()
    monkeypatch.setattr(
        me, "request", lambda *a, **k: pytest.fail("provider should not be called")
    )
    response = client.post(
        "/api/v1/shipping/quotes",
        json={
            "postal_code": "70000000",
            "items": [{"id": product_id, "name": "Batom Real", "quantity": 1}],
        },
    )
    assert response.status_code == 409


@pytest.mark.parametrize(
    "change", ["expired", "quantity", "price", "address", "service", "environment"]
)
def test_checkout_rejects_stale_or_changed_shipping_before_charging(
    monkeypatch, change
):
    product_id = setup_product()
    quote = make_quote(monkeypatch, product_id)
    payload, headers, captured = checkout(monkeypatch, product_id, quote)
    with Session(engine) as session:
        stored = session.get(ShippingQuote, UUID(quote["id"]))
        if change == "expired":
            stored.expires_at = utc_now() - timedelta(seconds=1)
        if change == "environment":
            stored.environment = "production"
        if change == "price":
            product = session.get(Product, UUID(product_id))
            product.price = 60
            session.add(product)
        session.add(stored)
        session.commit()
    if change == "quantity":
        payload["items"][0]["quantity"] = 2
    if change == "address":
        with Session(engine) as session:
            address = session.get(Address, UUID(payload["address_id"]))
            address.cep = "01001000"
            session.add(address)
            session.commit()
    if change == "service":
        payload["shipping"]["service_id"] = 9999
    response = client.post("/api/v1/payments/checkout", json=payload, headers=headers)
    assert response.status_code in (409, 422), response.text
    assert captured == {}
    with Session(engine) as session:
        assert session.exec(select(Stock)).one().total_quantity == 20
        assert not session.exec(select(Payment)).all()


def test_checkout_includes_freight_and_snapshots_recipient(monkeypatch):
    product_id = setup_product()
    quote = make_quote(monkeypatch, product_id)
    payload, headers, captured = checkout(monkeypatch, product_id, quote)
    response = client.post("/api/v1/payments/checkout", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    assert captured["shipping_amount"] == Decimal("18.60")
    with Session(engine) as session:
        payment = session.exec(select(Payment)).one()
        shipment = session.exec(select(Shipment)).one()
        assert payment.amount == Decimal("68.50")
        assert shipment.recipient["phone"] == "11999999999"
        assert shipment.customer_price == Decimal("18.60")
        assert len(session.exec(select(PaymentItem)).all()) == 1
    order_id = response.json()["order_id"]
    other = {"Authorization": f"Bearer {create_logged_user('other@example.com')}"}
    assert (
        client.get(f"/api/v1/shipping/orders/{order_id}", headers=other).status_code
        == 404
    )
    assert (
        client.get("/api/v1/shipping/admin/shipments", headers=headers).status_code
        == 403
    )
    out = client.get(f"/api/v1/shipping/orders/{order_id}", headers=headers).json()
    assert "recipient" not in out and "invoice_key" not in out


def make_shipment(monkeypatch):
    product_id = setup_product()
    quote = make_quote(monkeypatch, product_id)
    payload, headers, captured = checkout(monkeypatch, product_id, quote)
    result = client.post(
        "/api/v1/payments/checkout", json=payload, headers=headers
    ).json()
    with Session(engine) as session:
        payment = session.exec(select(Payment)).one()
        payment.status = "approved"
        session.add(payment)
        session.commit()
    admin = {"Authorization": f"Bearer {create_admin_token()}"}
    return result["order_id"], admin


def test_full_label_lifecycle_checks_async_generation_and_no_double_payment(
    monkeypatch,
):
    order_id, admin = make_shipment(monkeypatch)
    label_id = str(uuid4())
    calls = []
    remote_status = "pending"

    def request(session, method, path, **kwargs):
        nonlocal remote_status
        calls.append(path)
        if path.endswith("/cart"):
            body = kwargs["body"]
            assert body["options"]["non_commercial"] is False
            assert len(body["options"]["invoice"]["key"]) == 44
            assert body["products"][0]["unitary_value"] == 49.9
            return {"id": label_id, "status": "pending", "price": 18.6}
        if path.endswith("/checkout"):
            remote_status = "released"
            return {"purchase": {"status": "paid"}}
        if path.endswith("/generate"):
            return {label_id: {"status": True}}
        if path.endswith("/tracking"):
            return {label_id: {"status": remote_status, "tracking": "ME123BR"}}
        if path.endswith("/print"):
            assert kwargs["body"]["mode"] == "private"
            return {"url": "https://sandbox.melhorenvio.com.br/imprimir/test"}
        pytest.fail(path)

    monkeypatch.setattr(me, "request", request)
    base = f"/api/v1/shipping/admin/shipments/{order_id}"
    assert client.post(base + "/pay", headers=admin).status_code == 409
    assert (
        client.post(
            base + "/prepare", headers=admin, json={"invoice_key": "1" * 44}
        ).json()["status"]
        == "carted"
    )
    assert (
        client.post(
            base + "/prepare", headers=admin, json={"invoice_key": "1" * 44}
        ).status_code
        == 409
    )
    assert client.post(base + "/pay", headers=admin).json()["status"] == "paid"
    assert client.post(base + "/pay", headers=admin).status_code == 409
    assert calls.count("/api/v2/me/shipment/checkout") == 1
    assert (
        client.post(base + "/generate", headers=admin).json()["status"] == "generating"
    )
    assert client.post(base + "/print", headers=admin).status_code == 409
    assert client.post(base + "/sync", headers=admin).json()["status"] == "generating"
    remote_status = "generated"
    assert client.post(base + "/sync", headers=admin).json()["status"] == "ready"
    assert (
        client.post(base + "/print", headers=admin)
        .json()["print_url"]
        .startswith("https://")
    )
    remote_status = "delivered"
    assert client.post(base + "/sync", headers=admin).json()["status"] == "delivered"


def test_ambiguous_create_is_not_retried(monkeypatch):
    order_id, admin = make_shipment(monkeypatch)
    calls = []

    def request(*args, **kwargs):
        calls.append(args[2])
        raise HTTPException(502, "Provider unavailable")

    monkeypatch.setattr(me, "request", request)
    url = f"/api/v1/shipping/admin/shipments/{order_id}/prepare"
    assert (
        client.post(url, headers=admin, json={"invoice_key": "1" * 44}).status_code
        == 502
    )
    assert (
        client.post(url, headers=admin, json={"invoice_key": "1" * 44}).status_code
        == 409
    )
    assert len(calls) == 1


def test_oauth_cookie_state_one_time_and_encrypted_tokens(monkeypatch):
    monkeypatch.setattr(settings, "MELHOR_ENVIO_CLIENT_ID", "123")
    monkeypatch.setattr(settings, "MELHOR_ENVIO_CLIENT_SECRET", "app-test")
    admin = {"Authorization": f"Bearer {create_admin_token()}"}
    response = client.post("/api/v1/shipping/admin/authorize", headers=admin)
    assert response.status_code == 200
    from urllib.parse import urlparse, parse_qs

    state = parse_qs(urlparse(response.json()["url"]).query)["state"][0]
    assert (
        client.get(
            "/api/v1/shipping/oauth/callback",
            params={"state": "wrong", "code": "example"},
        ).status_code
        == 400
    )
    monkeypatch.setattr(
        me,
        "transport",
        lambda *a, **k: {
            "access_token": "example-access",
            "refresh_token": "example-refresh",
            "expires_in": 3600,
        },
    )
    response = client.get(
        "/api/v1/shipping/oauth/callback",
        params={"state": state, "code": "example"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with Session(engine) as session:
        connection = session.get(ShippingConnection, "sandbox")
        assert (
            connection.access_ciphertext != "example-access"
            and me.decrypt(connection.access_ciphertext) == "example-access"
        )
        assert connection.state_digest is None
    assert (
        client.get(
            "/api/v1/shipping/oauth/callback",
            params={"state": state, "code": "example"},
        ).status_code
        == 400
    )
    out = client.get("/api/v1/shipping/admin/connection", headers=admin).json()
    assert out["connected"] is True and "access_ciphertext" not in out


def test_expiring_oauth_token_is_rotated_before_request(monkeypatch):
    monkeypatch.setattr(settings, "MELHOR_ENVIO_CLIENT_ID", "123")
    monkeypatch.setattr(settings, "MELHOR_ENVIO_CLIENT_SECRET", "app-test")
    with Session(engine) as session:
        connection = ShippingConnection(environment="sandbox")
        me.store_tokens(
            connection,
            {
                "access_token": "old-access",
                "refresh_token": "old-refresh",
                "expires_in": 1,
            },
        )
        session.add(connection)
        session.commit()

        def transport(method, path, **kwargs):
            assert (
                kwargs["body"]["grant_type"] == "refresh_token"
                and kwargs["body"]["refresh_token"] == "old-refresh"
            )
            return {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
            }

        monkeypatch.setattr(me, "transport", transport)
        assert me.access_token(session) == "new-access"
        assert (
            me.decrypt(session.get(ShippingConnection, "sandbox").refresh_ciphertext)
            == "new-refresh"
        )


def test_brasilapi_lookup_cached_and_invalid_cep_does_not_call_provider(monkeypatch):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "cep": "01001000",
                "state": "SP",
                "city": "São Paulo",
                "street": "Praça da Sé",
                "neighborhood": "Sé",
            },
        )

    monkeypatch.setattr(
        brasil_api,
        "Client",
        lambda **kwargs: httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert client.get("/api/v1/brasil/cep/abc").status_code == 422
    for _ in range(2):
        response = client.get("/api/v1/brasil/cep/01001000")
        assert response.status_code == 200
        assert response.json()["street"] == "Praça da Sé"
    assert calls == ["https://brasilapi.com.br/api/cep/v2/01001000"]


@pytest.mark.parametrize("status", [404, 429, 500])
def test_brasilapi_unavailable_keeps_manual_entry_possible(monkeypatch, status):
    monkeypatch.setattr(
        brasil_api,
        "Client",
        lambda **kwargs: httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status, json={})
            )
        ),
    )
    response = client.get("/api/v1/brasil/cep/01001000")
    assert response.status_code == (404 if status == 404 else 503)
    assert "manual" in response.json()["detail"]


def test_lookups_are_throttled(monkeypatch):
    monkeypatch.setattr(brasil_api, "lookup_cep", lambda cep: {"cep": cep})
    monkeypatch.setattr(
        "app.api.v1.endpoints.brasilApi.lookup_cep", lambda cep: {"cep": cep}
    )
    for _ in range(30):
        assert client.get("/api/v1/brasil/cep/01001000").status_code == 200
    assert client.get("/api/v1/brasil/cep/01001000").status_code == 429


def test_multiple_correios_packages_keep_each_product_declaration(monkeypatch):
    order_id, admin = make_shipment(monkeypatch)
    with Session(engine) as session:
        shipment = session.exec(select(Shipment)).one()
        quote = session.get(ShippingQuote, shipment.quote_id)
        items = copy.deepcopy(quote.items)
        items[0]["quantity"] = 2
        services = copy.deepcopy(quote.services)
        service = next(item for item in services if item["id"] == shipment.service_id)
        service["company"] = "Correios"
        service["packages"] = [
            copy.deepcopy(service["packages"][0]),
            copy.deepcopy(service["packages"][0]),
        ]
        for package in service["packages"]:
            package["products"] = [{"id": items[0]["id"], "quantity": 1}]
        quote.items = items
        quote.services = services
        shipment.company_name = "Correios"
        session.add(quote)
        session.add(shipment)
        session.commit()
    calls = []

    def request(session, method, path, **kwargs):
        calls.append(kwargs["body"])
        return {"id": str(uuid4()), "status": "pending", "price": "12.50"}

    monkeypatch.setattr(me, "request", request)
    response = client.post(
        f"/api/v1/shipping/admin/shipments/{order_id}/prepare",
        headers=admin,
        json={"invoice_key": "1" * 44},
    )
    assert response.status_code == 200, response.text
    assert len(calls) == 2
    assert all(
        len(call["volumes"]) == 1 and call["products"][0]["quantity"] == 1
        for call in calls
    )
    assert response.json()["cost"] == 25
    assert len(response.json()["labels"]) == 2


def test_ambiguous_payment_is_reconciled_without_double_purchase(monkeypatch):
    order_id, admin = make_shipment(monkeypatch)
    label_id = str(uuid4())
    with Session(engine) as session:
        shipment = session.exec(select(Shipment)).one()
        shipment.status = "carted"
        shipment.labels = [{"id": label_id, "cost": "18.60"}]
        session.add(shipment)
        session.commit()
    calls = []

    def request(session, method, path, **kwargs):
        calls.append(path)
        if path.endswith("/checkout"):
            raise HTTPException(502, "Timeout after provider accepted the request")
        return {label_id: {"status": "released"}}

    monkeypatch.setattr(me, "request", request)
    base = f"/api/v1/shipping/admin/shipments/{order_id}"
    assert client.post(base + "/pay", headers=admin).status_code == 502
    assert client.post(base + "/pay", headers=admin).status_code == 409
    assert client.post(base + "/sync", headers=admin).json()["status"] == "paid"
    assert client.post(base + "/pay", headers=admin).status_code == 409
    assert calls.count("/api/v2/me/shipment/checkout") == 1


def test_reconcile_checks_order_tag_and_updates_actual_label_cost(monkeypatch):
    order_id, admin = make_shipment(monkeypatch)
    label_id = str(uuid4())
    with Session(engine) as session:
        shipment = session.exec(select(Shipment)).one()
        shipment.status = "needs_review"
        session.add(shipment)
        session.commit()
    wrong = True

    def request(session, method, path, **kwargs):
        if path.endswith("/search"):
            return [
                {
                    "id": label_id,
                    "service_id": 3,
                    "price": 22.5,
                    "tags": [{"tag": "another-order" if wrong else order_id}],
                    "to": {"postal_code": "70000000"},
                }
            ]
        return {label_id: {"status": "pending"}}

    monkeypatch.setattr(me, "request", request)
    base = f"/api/v1/shipping/admin/shipments/{order_id}/reconcile"
    assert (
        client.post(base, headers=admin, json={"label_ids": [label_id]}).status_code
        == 422
    )
    wrong = False
    response = client.post(base, headers=admin, json={"label_ids": [label_id]})
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "carted"
    assert response.json()["cost"] == 22.5


def test_stripe_receives_freight_as_its_own_line_item(monkeypatch):
    from app.services.checkoutService import create_checkout_session

    captured = {}

    def create(**kwargs):
        captured.update(kwargs)
        return {"id": "test-session"}

    monkeypatch.setattr("stripe.checkout.Session.create", create)
    create_checkout_session(
        [{"name": "Batom", "unit_price": Decimal("49.90"), "quantity": 2}],
        uuid4(),
        shipping_amount=Decimal("18.60"),
        shipping_name="Jadlog .Package",
        idempotency_key="integration-example",
    )
    lines = captured["line_items"]
    assert len(lines) == 2
    assert lines[0]["price_data"]["unit_amount"] == 4990 and lines[0]["quantity"] == 2
    assert lines[1]["price_data"]["unit_amount"] == 1860 and lines[1]["quantity"] == 1
    assert captured["idempotency_key"] == "integration-example"


def test_quotes_only_need_origin_cep_not_full_sender(monkeypatch):
    product_id = setup_product()
    monkeypatch.setattr(
        settings, "MELHOR_ENVIO_SENDER", json.dumps({"postal_code": "01001000"})
    )
    quote = make_quote(monkeypatch, product_id)
    assert quote["postal_code"] == "70000000"


def test_incomplete_sender_still_blocks_checkout_before_stripe(monkeypatch):
    product_id = setup_product()
    monkeypatch.setattr(
        settings, "MELHOR_ENVIO_SENDER", json.dumps({"postal_code": "01001000"})
    )
    quote = make_quote(monkeypatch, product_id)
    payload, headers, captured = checkout(monkeypatch, product_id, quote)
    response = client.post("/api/v1/payments/checkout", json=payload, headers=headers)
    assert response.status_code == 503
    assert captured == {}
    with Session(engine) as session:
        assert session.exec(select(Stock)).one().total_quantity == 20
        assert not session.exec(select(Payment)).all()
