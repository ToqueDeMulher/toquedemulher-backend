from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from app.core.settings import settings
from app.core.time import utc_now
from app.models.address import Address
from app.models.coupon import Coupon
from app.models.payment import Payment, PaymentStatus
from app.models.stock import Stock
from app.services import abacatepay, coupon_service
from tests.test_auth import (  # noqa: F401
    clean_db,
    client,
    create_admin_token,
    create_logged_user,
    engine,
)
from tests.test_shipping import checkout, config, make_quote, setup_product  # noqa: F401

CHECKOUT = "/api/v1/payments/checkout"
VALIDATE = "/api/v1/coupons/validate"
ADMIN = "/api/v1/admin/coupons"
# Produto de R$ 49,90 + frete de R$ 18,60 (serviço 3 da cotação de teste).


@pytest.fixture(autouse=True)
def provider(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "abacatepay")
    monkeypatch.setattr(settings, "ABACATEPAY_API_KEY", "dummy-dev-token")
    monkeypatch.setattr(settings, "ABACATEPAY_DEV_MODE", True)
    monkeypatch.setattr(settings, "ABACATEPAY_CARD_ENABLED", False)
    charged = []

    def create_remote(payment, **kwargs):
        charged.append(abacatepay.cents(payment.amount))
        return {
            "id": "pix_char_" + str(payment.order_id),
            "status": "PENDING",
            "amount": abacatepay.cents(payment.amount),
            "devMode": True,
            "brCode": "fixture-code",
            "brCodeBase64": "data:image/png;base64,aGVsbG8=",
            "expiresAt": "2030-01-01T12:00:00Z",
        }

    def no_network(*args, **kwargs):
        raise AssertionError("teste de cupom não deve chamar a AbacatePay")

    monkeypatch.setattr(abacatepay, "create_remote", create_remote)
    monkeypatch.setattr(abacatepay.httpx, "request", no_network)
    return charged


def add_coupon(**fields) -> str:
    data = {
        "code": "BEMVINDA10",
        "discount_type": "percent",
        "discount_value": 10,
        **fields,
    }
    with Session(engine) as session:
        session.add(Coupon(**data))
        session.commit()
    return data["code"]


def order(monkeypatch, coupon_code=None):
    product_id = setup_product()
    payload, headers, _ = checkout(
        monkeypatch, product_id, make_quote(monkeypatch, product_id)
    )
    if coupon_code:
        payload["coupon_code"] = coupon_code
    return payload, headers


def other_buyer(payload, email):
    token = create_logged_user(email)
    headers = {"Authorization": f"Bearer {token}"}
    user = client.get("/api/v1/user/me", headers=headers).json()
    with Session(engine) as session:
        address = Address(
            user_id=UUID(user["id"]),
            cep="70000000",
            street="Rua B",
            number="20",
            neighborhood="Centro",
            city="Brasília",
            state="DF",
        )
        session.add(address)
        session.commit()
        address_id = str(address.id)
    return {**payload, "address_id": address_id, "idempotency_key": str(uuid4())}, headers


def payments():
    with Session(engine) as session:
        return session.exec(select(Payment)).all()


def set_status(status):
    with Session(engine) as session:
        for payment in session.exec(select(Payment)).all():
            payment.status = status
            session.add(payment)
        session.commit()


def test_percent_coupon_discounts_only_products(monkeypatch, provider):
    add_coupon()
    payload, headers = order(monkeypatch, " bemvinda10 ")

    response = client.post(CHECKOUT, json=payload, headers=headers)

    assert response.status_code == 200, response.text
    [payment] = payments()
    assert payment.discount_amount == Decimal("4.99")  # 10% de 49,90, sem o frete
    assert payment.amount == Decimal("63.51")
    assert payment.coupon_id is not None
    assert provider == [6351]
    status = client.get(
        f"{CHECKOUT}/{response.json()['session_id']}", headers=headers
    ).json()
    assert status["amount"] == 63.51
    assert status["discount_amount"] == 4.99


def test_fixed_coupon_never_discounts_shipping(monkeypatch, provider):
    add_coupon(code="CEMREAIS", discount_type="fixed", discount_value=100)
    payload, headers = order(monkeypatch, "CEMREAIS")

    assert client.post(CHECKOUT, json=payload, headers=headers).status_code == 200
    [payment] = payments()
    assert payment.discount_amount == Decimal("49.90")
    assert payment.amount == Decimal("18.60")
    assert provider == [1860]


def test_discount_rounds_to_cents_and_respects_minimum_charge():
    percent = Coupon(code="X", discount_type="percent", discount_value=15)
    fixed = Coupon(code="Y", discount_type="fixed", discount_value=50)
    assert coupon_service.discount_for(percent, Decimal("49.90")) == Decimal("7.49")
    assert coupon_service.discount_for(fixed, Decimal("49.90")) == Decimal("49.90")
    assert coupon_service.discount_for(
        fixed, Decimal("49.90"), limit=Decimal("48.90")
    ) == Decimal("48.90")
    assert coupon_service.discount_for(
        fixed, Decimal("0.50"), limit=Decimal("-0.50")
    ) == Decimal("0.00")


@pytest.mark.parametrize(
    "fields",
    [
        {"active": False},
        {"valid_to": utc_now().replace(tzinfo=None) - timedelta(days=1)},
        {"valid_from": utc_now().replace(tzinfo=None) + timedelta(days=1)},
        {"code": "OUTRO"},
    ],
    ids=["inativo", "expirado", "ainda-nao-vale", "inexistente"],
)
def test_unusable_coupon_is_rejected_without_reserving_stock(
    monkeypatch, provider, fields
):
    add_coupon(**fields)
    payload, headers = order(monkeypatch, "BEMVINDA10")

    response = client.post(CHECKOUT, json=payload, headers=headers)

    assert response.status_code == 422
    assert response.json()["detail"] == coupon_service.INVALID
    assert payments() == []
    assert provider == []
    with Session(engine) as session:
        assert session.exec(select(Stock)).one().total_quantity == 20


def test_global_limit_counts_active_orders_and_frees_expired_ones(monkeypatch):
    add_coupon(code="LIMITE1", max_uses_global=1)
    payload, headers = order(monkeypatch, "LIMITE1")
    assert client.post(CHECKOUT, json=payload, headers=headers).status_code == 200

    second, second_headers = other_buyer(payload, "ana@example.com")
    response = client.post(CHECKOUT, json=second, headers=second_headers)
    assert response.status_code == 422
    assert response.json()["detail"] == "Este cupom esgotou."

    set_status(PaymentStatus.EXPIRED.value)
    second["idempotency_key"] = str(uuid4())
    assert client.post(CHECKOUT, json=second, headers=second_headers).status_code == 200


def test_per_user_limit_blocks_only_the_same_buyer(monkeypatch):
    add_coupon(code="UMAVEZ", max_uses_per_user=1)
    payload, headers = order(monkeypatch, "UMAVEZ")
    assert client.post(CHECKOUT, json=payload, headers=headers).status_code == 200
    set_status(PaymentStatus.APPROVED.value)

    payload["idempotency_key"] = str(uuid4())
    response = client.post(CHECKOUT, json=payload, headers=headers)
    assert response.status_code == 422
    assert "máximo" in response.json()["detail"]

    second, second_headers = other_buyer(payload, "ana@example.com")
    assert client.post(CHECKOUT, json=second, headers=second_headers).status_code == 200


def test_legacy_stripe_checkout_rejects_coupons(monkeypatch, provider):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "stripe")
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test")
    add_coupon()
    payload, headers = order(monkeypatch, "BEMVINDA10")

    response = client.post(CHECKOUT, json=payload, headers=headers)

    assert response.status_code == 422
    assert payments() == []


def test_validate_previews_discount_for_logged_buyer():
    add_coupon(code="PREVIA", discount_type="fixed", discount_value=5)
    product_id = setup_product()
    headers = {"Authorization": f"Bearer {create_logged_user()}"}
    body = {"code": "previa", "items": [{"id": product_id, "quantity": 2}]}

    response = client.post(VALIDATE, json=body, headers=headers)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "code": "PREVIA",
        "description": None,
        "discount_type": "fixed",
        "discount_value": 5.0,
        "items_subtotal": 99.8,
        "discount_amount": 5.0,
    }
    assert client.post(VALIDATE, json=body).status_code == 401
    body["code"] = "NAOEXISTE"
    assert client.post(VALIDATE, json=body, headers=headers).status_code == 422


def test_admin_creates_lists_and_updates_coupons():
    admin = {"Authorization": f"Bearer {create_admin_token()}"}
    buyer = {"Authorization": f"Bearer {create_logged_user()}"}
    body = {
        "code": " verao20 ",
        "discount_type": "percent",
        "discount_value": 20,
        "valid_from": "2026-01-01T00:00:00Z",
        "max_uses_global": 100,
    }

    assert client.post(ADMIN, json=body, headers=buyer).status_code == 403
    created = client.post(ADMIN, json=body, headers=admin)
    assert created.status_code == 201, created.text
    coupon = created.json()
    assert coupon["code"] == "VERAO20"
    assert coupon["uses"] == 0
    assert client.post(
        ADMIN, json={**body, "code": "Verao20"}, headers=admin
    ).status_code == 409
    assert client.post(
        ADMIN, json={**body, "code": "MUITO", "discount_value": 150}, headers=admin
    ).status_code == 422

    path = f"{ADMIN}/{coupon['id']}"
    updated = client.patch(path, json={"active": False}, headers=admin)
    assert updated.status_code == 200
    assert updated.json()["active"] is False
    assert updated.json()["discount_value"] == 20
    assert client.patch(path, json={"discount_value": 120}, headers=admin).status_code == 422
    # Data com fuso comparada à data gravada sem fuso: erro de validação, não 500.
    assert client.patch(
        path, json={"valid_to": "2025-12-31T21:00:00-03:00"}, headers=admin
    ).status_code == 422
    assert client.patch(f"{ADMIN}/999", json={}, headers=admin).status_code == 404

    listed = client.get(ADMIN, headers=admin)
    assert [item["code"] for item in listed.json()] == ["VERAO20"]
