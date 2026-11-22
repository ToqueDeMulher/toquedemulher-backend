import base64
import hmac
import json
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.api.v1.endpoints.abacatepay_webhook import SIGNING_KEY
from app.core.settings import settings
from app.models.payment import Payment
from app.models.shipping import Shipment
from app.models.stock import Stock
from app.models.stockMovement import StockMovement, StockMovementType
from app.services import abacatepay, melhor_envio
from app.services.shipment_service import prepare
from tests.test_auth import (  # noqa: F401
    clean_db,
    client,
    create_admin_token,
    create_logged_user,
    engine,
)
from tests.test_shipping import checkout, config, make_quote, setup_product  # noqa: F401

CHECKOUT = "/api/v1/payments/checkout"
WEBHOOK = "/api/v1/payments/webhooks/abacatepay"
PIX_ID = "pix_char_fixture"


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "abacatepay")
    monkeypatch.setattr(abacatepay, "CHECK_INTERVAL", timedelta(0))
    monkeypatch.setattr(settings, "ABACATEPAY_API_KEY", "dummy-dev-token")
    monkeypatch.setattr(settings, "ABACATEPAY_WEBHOOK_SECRET", "dummy-webhook-secret")
    monkeypatch.setattr(settings, "ABACATEPAY_DEV_MODE", True)
    monkeypatch.setattr(settings, "ABACATEPAY_CARD_ENABLED", False)
    remote = {
        "id": PIX_ID,
        "amount": 6850,
        "status": "PENDING",
        "devMode": True,
        "brCode": "000201-fixture",
        "brCodeBase64": "data:image/png;base64,iVBORw0KGgo=",
        "expiresAt": "2026-12-31T12:15:00.000Z",
    }
    state = {
        "emitted": False,
        "lose_response": False,
        "down": False,
        "posts": [],
        "reads": 0,
    }

    def request(method, url, *, params, json, headers, timeout, follow_redirects):
        assert headers == {"Authorization": "Bearer dummy-dev-token"}
        assert not follow_redirects
        if state["down"]:
            raise httpx.ConnectError("dummy unavailable")
        if method == "GET":
            state["reads"] += 1
            assert url == f"{abacatepay.API_URL}/transparents/list"
            if state["emitted"]:
                assert (
                    params.get("id") == PIX_ID
                    or params.get("externalId") == remote["metadata"]["order_id"]
                )
            return httpx.Response(
                200,
                json={"success": True, "data": [remote] if state["emitted"] else []},
                request=httpx.Request(method, url),
            )
        assert method == "POST" and url == f"{abacatepay.API_URL}/transparents/create"
        state["posts"].append(json)
        assert json["method"] == "PIX"
        assert json["data"]["amount"] == 6850
        assert json["data"]["expiresIn"] == 900
        assert json["data"]["externalId"] == json["data"]["metadata"]["order_id"]
        remote["metadata"] = json["data"]["metadata"]
        state["emitted"] = True
        if state["lose_response"]:
            raise httpx.ReadTimeout("dummy timeout")
        return httpx.Response(
            200,
            json={"success": True, "data": remote},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(abacatepay.httpx, "request", request)
    return remote, state


def make_order(monkeypatch):
    product_id = setup_product()
    return checkout(monkeypatch, product_id, make_quote(monkeypatch, product_id))[:2]


def deliver(
    event="transparent.completed",
    *,
    secret="dummy-webhook-secret",
    valid_signature=True,
    dev_mode=True,
):
    body = json.dumps(
        {
            "event": event,
            "id": "log_fixture",
            "apiVersion": 2,
            "devMode": dev_mode,
            "data": {"transparent": {"id": PIX_ID, "status": "PAID", "amount": 6850}},
        }
    ).encode()
    signature = base64.b64encode(hmac.digest(SIGNING_KEY, body, "sha256")).decode()
    return client.post(
        WEBHOOK,
        params={"webhookSecret": secret},
        content=body,
        headers={"X-Webhook-Signature": signature if valid_signature else "forged"},
    )


def test_pix_checkout_rechecks_server_price_and_releases_order_after_authenticated_payment(
    monkeypatch, provider
):
    remote, state = provider
    payload, headers = make_order(monkeypatch)
    payload["items"][0]["unit_price"] = 0.01
    payload["amount"] = 1
    created = client.post(CHECKOUT, json=payload, headers=headers)
    assert created.status_code == 200, created.text
    order = created.json()
    path = f"{CHECKOUT}/{order['session_id']}"
    pending = client.get(path, headers=headers)
    assert pending.headers["cache-control"] == "no-store"
    assert pending.json()["pix"]["code"] == "000201-fixture"
    assert pending.json()["status"] == "pending"
    assert len(state["posts"]) == 1

    with Session(engine) as session:
        payment = session.exec(select(Payment)).one()
        shipment = session.exec(select(Shipment)).one()
        assert payment.provider_session_id == PIX_ID
        assert str(payment.amount) == "68.50"
        with pytest.raises(HTTPException, match="Aguarde a confirmação"):
            prepare(session, shipment, payment, None)

    assert deliver(valid_signature=False).status_code == 403
    assert deliver(secret="wrong").status_code == 403
    assert deliver(dev_mode=False).status_code == 400
    assert deliver().status_code == 503  # signed body alone cannot approve
    assert client.get(path, headers=headers).json()["status"] == "pending"

    remote["status"] = "PAID"
    remote["amount"] = 1
    assert deliver().status_code == 502
    remote["amount"] = 6850
    assert deliver().json() == {"status": "approved"}
    assert deliver().json() == {"status": "approved"}
    assert client.get(path, headers=headers).json()["status"] == "approved"
    admin = {"Authorization": f"Bearer {create_admin_token()}"}
    shipment_url = f"/api/v1/shipping/admin/shipments/{order['order_id']}"
    invoice = {"invoice_key": "1" * 44}
    with monkeypatch.context() as live:
        live.setattr(settings, "MELHOR_ENVIO_ENVIRONMENT", "production")
        with Session(engine) as session:
            payment = session.exec(select(Payment)).one()
            shipment = session.exec(select(Shipment)).one()
            with pytest.raises(HTTPException, match="Pagamento de teste"):
                prepare(session, shipment, payment, invoice["invoice_key"])

    def ship(session, method, path, **kwargs):
        assert (method, path) == ("POST", "/api/v2/me/cart")
        return {"id": str(uuid4()), "status": "pending", "price": 18.60}

    monkeypatch.setattr(melhor_envio, "request", ship)
    assert (
        client.post(shipment_url + "/prepare", headers=admin, json=invoice).json()[
            "status"
        ]
        == "carted"
    )

    # A genuine refund puts fulfillment on hold even while read-back is stale.
    assert deliver("transparent.refunded").status_code == 503
    assert client.get(path, headers=headers).json()["status"] == "refund_pending"
    assert client.post(shipment_url + "/pay", headers=admin).status_code == 409
    assert deliver().json() == {"status": "refund_pending"}
    remote["status"] = "REFUNDED"
    assert deliver("transparent.refunded").json() == {"status": "refunded"}
    remote["status"] = "PAID"
    assert deliver().json() == {"status": "refunded"}
    with Session(engine) as session:
        assert session.exec(select(Payment)).one().status == "refunded"
        assert session.exec(select(Stock)).one().total_quantity == 19


def test_timeout_recovers_same_charge_and_keeps_one_reservation(monkeypatch, provider):
    _, state = provider
    payload, headers = make_order(monkeypatch)
    state["lose_response"] = True
    assert client.post(CHECKOUT, json=payload, headers=headers).status_code == 502
    active = client.get(f"{CHECKOUT}/active", headers=headers).json()
    state["down"] = True
    assert (
        client.get(f"{CHECKOUT}/{active['session_id']}", headers=headers).status_code
        == 502
    )
    state["down"] = False
    assert client.post(CHECKOUT, json=payload, headers=headers).json() == active
    assert len(state["posts"]) == 1
    payload["idempotency_key"] = str(uuid4())
    assert client.post(CHECKOUT, json=payload, headers=headers).status_code == 409
    with Session(engine) as session:
        assert len(session.exec(select(Payment)).all()) == 1
        assert session.exec(select(Stock)).one().total_quantity == 19


@pytest.mark.parametrize(
    ("remote_status", "local_status"),
    [
        ("EXPIRED", "expired"),
        ("CANCELLED", "cancelled"),
        ("FAILED", "rejected"),
    ],
)
def test_terminal_unpaid_releases_stock_once(
    monkeypatch, provider, remote_status, local_status
):
    remote, _ = provider
    payload, headers = make_order(monkeypatch)
    created = client.post(CHECKOUT, json=payload, headers=headers).json()
    remote["status"] = remote_status
    path = f"{CHECKOUT}/{created['session_id']}"
    assert client.get(path, headers=headers).json()["status"] == local_status
    assert client.get(path, headers=headers).json()["pix"] is None
    assert deliver().json()["status"] == local_status
    remote["status"] = "PAID"
    assert deliver().status_code == 503
    assert client.get(path, headers=headers).json()["status"] == local_status
    with Session(engine) as session:
        assert session.exec(select(Stock)).one().total_quantity == 20
        returns = session.exec(
            select(StockMovement).where(
                StockMovement.movement_type == StockMovementType.RETURN
            )
        ).all()
        assert len(returns) == 1


def test_invalid_checkout_and_access_to_another_account_are_rejected(
    monkeypatch, provider
):
    _, state = provider
    payload, headers = make_order(monkeypatch)
    assert (
        client.post(
            CHECKOUT, json={**payload, "method": "CARD"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post(
            CHECKOUT, json={**payload, "items": []}, headers=headers
        ).status_code
        == 422
    )
    assert state["posts"] == []
    order = client.post(CHECKOUT, json=payload, headers=headers).json()
    other = {"Authorization": f"Bearer {create_logged_user('other@example.com')}"}
    assert (
        client.get(f"{CHECKOUT}/{order['session_id']}", headers=other).status_code
        == 404
    )
    assert (
        client.post(f"{CHECKOUT}/{order['order_id']}/resume", headers=other).status_code
        == 404
    )
    assert client.post(CHECKOUT, json=payload, headers=other).status_code == 409


def test_stripe_webhook_cannot_change_an_abacatepay_order(monkeypatch, provider):
    payload, headers = make_order(monkeypatch)
    order = client.post(CHECKOUT, json=payload, headers=headers).json()
    monkeypatch.setattr(
        "stripe.Webhook.construct_event",
        lambda **kwargs: {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": PIX_ID,
                    "payment_status": "paid",
                    "amount_total": 6850,
                    "currency": "brl",
                    "metadata": {"order_id": order["order_id"]},
                }
            },
        },
    )
    response = client.post(
        "/api/v1/payments/webhook", headers={"Stripe-Signature": "fixture"}
    )
    assert response.status_code == 503
    with Session(engine) as session:
        assert session.exec(select(Payment)).one().status == "pending"


def test_hosted_card_timeout_is_never_reposted_and_exact_paid_amount_is_required(
    monkeypatch, provider
):
    monkeypatch.setattr(settings, "ABACATEPAY_CARD_ENABLED", True)
    payload, headers = make_order(monkeypatch)
    payload["method"] = "CARD"
    requests = []
    charge = None
    visible = False

    def request(method, url, *, params, json, **kwargs):
        nonlocal charge
        path = url.removeprefix(f"{abacatepay.API_URL}/")
        requests.append((method, path))
        response_code = 200
        if path == "products/get":
            assert params == {"externalId": "tdm-brl-6850"}
            data = {
                "id": "prod_fixture",
                "externalId": "tdm-brl-6850",
                "price": 6850,
                "currency": "BRL",
                "devMode": True,
            }
        elif path == "checkouts/create":
            assert json["methods"] == ["CARD"]
            assert json["items"] == [{"id": "prod_fixture", "quantity": 1}]
            assert json["completionUrl"].endswith(f"?session_id={json['externalId']}")
            charge = {
                "id": "bill_fixture",
                "externalId": json["externalId"],
                "status": "PENDING",
                "amount": 6850,
                "devMode": True,
                "url": "https://app.abacatepay.com/pay/bill_fixture",
            }
            raise httpx.ReadTimeout("checkout response lost")
        else:
            assert path == "checkouts/get"
            data = charge if visible else None
            response_code = 200 if visible else 404
        return httpx.Response(
            response_code,
            json={"success": True, "data": data},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(abacatepay.httpx, "request", request)
    assert client.post(CHECKOUT, json=payload, headers=headers).status_code == 502
    assert client.post(CHECKOUT, json=payload, headers=headers).status_code == 503
    visible = True
    response = client.post(CHECKOUT, json=payload, headers=headers)
    assert response.json()["checkout_url"] == charge["url"]
    assert requests.count(("POST", "checkouts/create")) == 1
    path = f"{CHECKOUT}/{response.json()['session_id']}"
    charge.update(status="PAID", paidAmount=1)
    assert client.get(path, headers=headers).status_code == 502
    charge["paidAmount"] = 6850
    assert client.get(path, headers=headers).json()["status"] == "approved"


def test_reconciliation_releases_abandoned_pix_reservation(monkeypatch, provider):
    from app.core.db import Database
    from app.core.time import utc_now
    from scripts import reconcile_abacatepay

    remote, _ = provider
    payload, headers = make_order(monkeypatch)
    assert client.post(CHECKOUT, json=payload, headers=headers).status_code == 200
    with Session(engine) as session:
        payment = session.exec(select(Payment)).one()
        payment.provider_checked_at = utc_now() - timedelta(minutes=2)
        session.commit()
    remote["status"] = "EXPIRED"
    monkeypatch.setattr(Database, "engine", engine)
    assert reconcile_abacatepay.run(1) == 0
    with Session(engine) as session:
        assert session.exec(select(Payment)).one().status == "expired"
        assert session.exec(select(Stock)).one().total_quantity == 20


def test_status_throttle_serves_cached_pix_without_remote_requests(
    monkeypatch, provider
):
    _, state = provider
    monkeypatch.setattr(abacatepay, "CHECK_INTERVAL", timedelta(seconds=6))
    payload, headers = make_order(monkeypatch)
    order = client.post(CHECKOUT, json=payload, headers=headers).json()
    status_url = f"{CHECKOUT}/{order['session_id']}"
    for _ in range(3):
        assert (
            client.get(status_url, headers=headers).json()["pix"]["code"]
            == "000201-fixture"
        )
    assert state["reads"] == 0


def test_card_details_reject_redirect_to_an_untrusted_origin():
    payment = Payment(provider_method="CARD", status="pending")
    with pytest.raises(HTTPException) as rejected:
        abacatepay.payment_details(
            payment, {"url": "https://app.abacatepay.com.evil.test/pay/bill_x"}
        )
    assert rejected.value.status_code == 502
