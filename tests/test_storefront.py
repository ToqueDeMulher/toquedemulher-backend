from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from tests.test_auth import client, engine, clean_db, create_admin_token, override_get_db
from tests.test_shipping import setup_product, make_quote, checkout, config
from app.core.db import Database
from app.core.settings import settings
from app.main import app
from app.models.category import Category
from app.models.description import Description
from app.models.product import Product
from app.models.productImage import ProductImage
from app.models.stock import Stock
from app.models.payment import Payment
from app.models.stockMovement import StockMovement, StockMovementType


def test_public_catalog_uses_persisted_categories_details_images_and_stock():
    with Session(engine) as session:
        product = Product(name="Perfume cadastrado", slug="perfume-cadastrado", price=199.9,
                          volume="50 ml", color="Rosa", categories=[Category(name="Perfumes")],
                          description=Description(text="Descrição cadastrada", ingredients="Composição cadastrada", usage_tips="Uso cadastrado"))
        session.add(product)
        session.flush()
        session.add_all([Stock(product_id=product.id, total_quantity=3),
                         ProductImage(product_id=product.id, url="/foto2.jpg", order=2),
                         ProductImage(product_id=product.id, url="/foto1.jpg", order=1),
                         Product(name="Oculto", slug="oculto", price=10, active=False)])
        session.commit()
        product_id = str(product.id)
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert len(response.json()) == 1
    data = response.json()[0]
    assert data["id"] == product_id and data["category"] == "perfumes"
    assert data["categories"] == ["perfumes"]
    assert data["description"] == "Descrição cadastrada" and data["composition"] == "Composição cadastrada"
    assert data["color"] == "Rosa" and data["volume"] == "50 ml"
    assert data["images"][0]["url"] == data["image"] == "/foto1.jpg"
    assert data["available"] is True and data["stockQuantity"] == 3
    assert data["reviews"] == data["rating"] == 0 and "isNew" not in data
    assert client.get(f"/api/v1/products/{product_id}").json() == data


def test_admin_changes_reflect_in_catalog_and_missing_stock_is_unavailable():
    product_id = setup_product()
    token = create_admin_token()
    response = client.patch(f"/api/v1/products/{product_id}",
        headers={"Authorization": f"Bearer {token}"}, json={"price": 75.5})
    assert response.status_code == 200
    assert client.get("/api/v1/products").json()[0]["price"] == 75.5
    with Session(engine) as session:
        session.delete(session.exec(select(Stock)).one())
        session.commit()
    data = client.get(f"/api/v1/products/{product_id}").json()
    assert not data["available"] and data["category"] is None
    client.patch(f"/api/v1/products/{product_id}", headers={"Authorization": f"Bearer {token}"}, json={"active": False})
    assert client.get("/api/v1/products").json() == []
    assert client.get(f"/api/v1/products/{product_id}").status_code == 404


@pytest.mark.parametrize("bad_id", ["1", str(uuid4())])
def test_shipping_never_matches_a_product_by_name(monkeypatch, bad_id):
    setup_product()
    monkeypatch.setattr("app.services.melhor_envio.request", lambda *a, **k: pytest.fail("Must reject before provider"))
    response = client.post("/api/v1/shipping/quotes", json={"postal_code": "70040010", "items": [{"id": bad_id, "name": "Batom Real", "quantity": 1}]})
    assert response.status_code == 404


def test_public_cep_quote_includes_product_ids_and_real_provider_terms(monkeypatch):
    product_id = setup_product()
    result = make_quote(monkeypatch, product_id, postal_code="70040010")
    assert result["postal_code"] == "70040010"
    assert result["item_prices"][0]["id"] == product_id
    assert result["services"] and all(service["delivery_max"] >= service["delivery_min"] for service in result["services"])


def test_contact_requires_valid_data_and_smtp_acceptance(monkeypatch):
    monkeypatch.setattr(settings, "CONTACT_RECIPIENT_EMAIL", "support@example.test")
    payload = {"name": "Cliente", "email": "cliente@example.com", "subject": "Pedido", "message": "Preciso de ajuda com meu pedido <script>."}
    captured = []
    def send(*args):
        captured.append(args)
        return False
    monkeypatch.setattr("app.api.v1.endpoints.contact.send_email", send)
    assert client.post("/api/v1/contact", json={**payload, "email": "invalid"}).status_code == 422
    assert client.post("/api/v1/contact", json={**payload, "subject": "Pedido\r\nBcc: bad"}).status_code == 422
    assert not captured
    assert client.post("/api/v1/contact", json=payload).status_code == 503
    assert "&lt;script&gt;" in captured[0][2]
    monkeypatch.setattr("app.api.v1.endpoints.contact.send_email", lambda *a: True)
    assert client.post("/api/v1/contact", json=payload).status_code == 202
    monkeypatch.setattr(settings, "CONTACT_RECIPIENT_EMAIL", "")
    assert client.post("/api/v1/contact", json=payload).status_code == 503


def test_startup_does_not_require_database_or_execute_ddl(monkeypatch):
    monkeypatch.setattr(settings, "CREATE_TABLES_ON_STARTUP", False)
    monkeypatch.setattr(Database, "create_db_and_tables", lambda: pytest.fail("Startup must not write schema"))
    with TestClient(app) as isolated:
        assert isolated.get("/health").json() == {"status": "ok"}


def test_database_failure_is_a_portuguese_503_with_cors():
    def unavailable():
        raise OperationalError("SELECT", {}, Exception("EAUTHQUERY"))
        yield
    app.dependency_overrides[Database.get_session] = unavailable
    try:
        response = client.get("/api/v1/products", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 503
        assert "Tente novamente" in response.json()["detail"]
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert "EAUTHQUERY" not in response.text
    finally:
        app.dependency_overrides[Database.get_session] = override_get_db


def test_cancel_confirmed_expired_session_releases_stock_once(monkeypatch):
    product_id = setup_product()
    quote = make_quote(monkeypatch, product_id)
    payload, headers, _ = checkout(monkeypatch, product_id, quote)
    order = client.post("/api/v1/payments/checkout", json=payload, headers=headers).json()["order_id"]
    def already_expired(session_id):
        raise RuntimeError("Response lost")
    monkeypatch.setattr("app.api.v1.endpoints.stripeCheckout.expire_checkout_session", already_expired)
    monkeypatch.setattr("app.api.v1.endpoints.stripeCheckout.retrieve_checkout_session", lambda session_id: {"status": "expired"})
    url = f"/api/v1/payments/checkout/{order}/cancel"
    assert client.post(url, headers=headers).json()["status"] == "cancelled"
    assert client.post(url, headers=headers).json()["status"] == "cancelled"
    with Session(engine) as session:
        assert session.exec(select(Stock)).one().total_quantity == 20
        assert len(session.exec(select(StockMovement).where(StockMovement.movement_type == StockMovementType.RETURN)).all()) == 1


def test_failed_cancellation_never_releases_stock(monkeypatch):
    product_id = setup_product()
    quote = make_quote(monkeypatch, product_id)
    payload, headers, _ = checkout(monkeypatch, product_id, quote)
    order = client.post("/api/v1/payments/checkout", json=payload, headers=headers).json()["order_id"]
    monkeypatch.setattr("app.api.v1.endpoints.stripeCheckout.expire_checkout_session", lambda *a: (_ for _ in ()).throw(RuntimeError("timeout")))
    monkeypatch.setattr("app.api.v1.endpoints.stripeCheckout.retrieve_checkout_session", lambda *a: {"status": "complete"})
    assert client.post(f"/api/v1/payments/checkout/{order}/cancel", headers=headers).status_code == 502
    with Session(engine) as session:
        assert session.exec(select(Stock)).one().total_quantity == 19
        assert session.exec(select(Payment)).one().status == "pending"


def test_checkout_accepts_only_ids_quantities_and_server_prices(monkeypatch):
    product_id = setup_product()
    quote = make_quote(monkeypatch, product_id)
    payload, headers, captured = checkout(monkeypatch, product_id, quote)
    payload["items"] = [{"id": product_id, "quantity": 1}]
    response = client.post("/api/v1/payments/checkout", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    with Session(engine) as session:
        payment = session.exec(select(Payment)).one()
        assert str(payment.amount) == "68.50"
        session_id = payment.provider_session_id
    # Browser status reads cannot approve the payment.
    assert client.get(f"/api/v1/payments/checkout/{session_id}", headers=headers).json()["status"] == "pending"
    assert captured["shipping_amount"] > 0


def test_completed_pending_then_approved_repeated_webhooks_keep_stock_reserved(monkeypatch):
    product_id = setup_product()
    quote = make_quote(monkeypatch, product_id)
    payload, headers, _ = checkout(monkeypatch, product_id, quote)
    result = client.post("/api/v1/payments/checkout", json=payload, headers=headers).json()
    event = {"type": "checkout.session.completed", "data": {"object": {
        "id": result["session_id"], "payment_status": "unpaid", "payment_intent": "pi_test",
        "metadata": {"order_id": result["order_id"]},
    }}}
    monkeypatch.setattr("stripe.Webhook.construct_event", lambda **kwargs: event)
    def deliver():
        return client.post("/api/v1/payments/webhook", content=b"{}", headers={"stripe-signature": "test"})
    assert deliver().json()["payment_status"] == "pending"
    event["data"]["object"]["payment_status"] = "paid"
    assert deliver().json()["payment_status"] == "approved"
    assert deliver().json()["duplicate"] is True
    event["type"] = "checkout.session.expired"
    assert deliver().json()["payment_status"] == "approved"
    with Session(engine) as session:
        assert session.exec(select(Stock)).one().total_quantity == 19


def test_early_webhook_requests_retry_instead_of_losing_confirmation(monkeypatch):
    event = {"type": "checkout.session.completed", "data": {"object": {
        "id": "cs_not_committed", "payment_status": "paid", "metadata": {"order_id": str(uuid4())},
    }}}
    monkeypatch.setattr("stripe.Webhook.construct_event", lambda **kwargs: event)
    assert client.post("/api/v1/payments/webhook", content=b"{}", headers={"stripe-signature": "test"}).status_code == 503
