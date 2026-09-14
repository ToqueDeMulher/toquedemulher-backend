"""
Testes de autenticacao da API ativa.
Execute com: pytest tests/ -v
"""
import os
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("FRONTEND_SUCCESS_URL", "http://localhost/success")
os.environ.setdefault("FRONTEND_PENDING_URL", "http://localhost/pending")
os.environ.setdefault("FRONTEND_FAILURE_URL", "http://localhost/failure")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")

from app.core.db import Database  # noqa: E402
from app.core.settings import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models.address import Address  # noqa: E402
from app.models.payment import Payment, PaymentStatus  # noqa: E402
from app.models.paymentItem import PaymentItem  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.productReview import ProductReview  # noqa: E402
from app.models.stock import Stock  # noqa: E402
from app.models.stockMovement import StockMovement, StockMovementType  # noqa: E402
from app.models.user import UserInDB  # noqa: E402
from app.services.email_confirmation_service import create_email_confirmation_token  # noqa: E402
from app.services.loginService import LoginAndJWT  # noqa: E402


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_db():
    with Session(engine) as db:
        yield db


app.dependency_overrides[Database.get_session] = override_get_db
SQLModel.metadata.create_all(bind=engine)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    SQLModel.metadata.drop_all(bind=engine)
    SQLModel.metadata.create_all(bind=engine)
    yield


def create_logged_user(email: str = "maria@example.com") -> str:
    client.post(
        "/api/v1/user/register",
        json={
            "name": "Maria Silva",
            "email": email,
            "password": "Senha@123",
        },
    )
    login_response = client.post(
        "/api/v1/user/login",
        json={
            "email": email,
            "password": "Senha@123",
        },
    )
    return login_response.json()["access_token"]


def create_admin_token(email: str = "admin@example.com") -> str:
    with Session(engine) as session:
        admin = UserInDB(
            name="Admin Toque de Mulher",
            email=email,
            hashed_password=LoginAndJWT.hashing_password("Senha@123"),
            role="admin",
        )
        session.add(admin)
        session.commit()

    login_response = client.post(
        "/api/v1/user/login",
        json={
            "email": email,
            "password": "Senha@123",
        },
    )
    return login_response.json()["access_token"]


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize("path", ["/api/v1/user/login", "/api/v1/user/register"])
@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
)
def test_auth_preflight_accepts_frontend_origins(path, origin):
    response = client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "POST" in response.headers["access-control-allow-methods"]


@pytest.mark.parametrize("path", ["/api/v1/user/login", "/api/v1/user/register"])
def test_auth_preflight_rejects_unlisted_origin(path):
    response = client.options(
        path,
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_register_user():
    response = client.post(
        "/api/v1/user/register",
        json={
            "name": "Maria Silva",
            "email": "maria@example.com",
            "password": "Senha@123",
        },
    )

    assert response.status_code == 201
    assert (
        response.json()["mensagem"]
        == "Usuario criado com sucesso. Verifique seu email para confirmar a conta."
    )


def test_register_queues_confirmation_email(monkeypatch):
    sent_emails: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "app.api.v1.endpoints.user.send_confirmation_email",
        lambda name, email: sent_emails.append((name, email)) or True,
    )

    response = client.post(
        "/api/v1/user/register",
        json={
            "name": "Maria Silva",
            "email": "maria@example.com",
            "password": "Senha@123",
        },
    )

    assert response.status_code == 201
    assert sent_emails == [("Maria Silva", "maria@example.com")]


def test_confirm_email_marks_user_as_confirmed():
    email = "maria@example.com"
    client.post(
        "/api/v1/user/register",
        json={
            "name": "Maria Silva",
            "email": email,
            "password": "Senha@123",
        },
    )

    token = create_email_confirmation_token(email)
    response = client.post(
        "/api/v1/user/confirm-email",
        json={"token": token},
    )

    assert response.status_code == 200
    assert response.json()["mensagem"] == "Email confirmado com sucesso"

    with Session(engine) as session:
        user = session.exec(select(UserInDB).where(UserInDB.email == email)).one()
        assert user.email_confirmed_at is not None


def test_login_can_require_confirmed_email(monkeypatch):
    email = "maria@example.com"
    monkeypatch.setattr(settings, "EMAIL_CONFIRMATION_REQUIRED", True)
    client.post(
        "/api/v1/user/register",
        json={
            "name": "Maria Silva",
            "email": email,
            "password": "Senha@123",
        },
    )

    blocked_response = client.post(
        "/api/v1/user/login",
        json={
            "email": email,
            "password": "Senha@123",
        },
    )
    assert blocked_response.status_code == 403

    client.post(
        "/api/v1/user/confirm-email",
        json={"token": create_email_confirmation_token(email)},
    )
    login_response = client.post(
        "/api/v1/user/login",
        json={
            "email": email,
            "password": "Senha@123",
        },
    )
    assert login_response.status_code == 200


def test_register_duplicate_email():
    user_data = {
        "name": "Maria Silva",
        "email": "maria@example.com",
        "password": "Senha@123",
    }

    client.post("/api/v1/user/register", json=user_data)
    response = client.post("/api/v1/user/register", json=user_data)

    assert response.status_code == 400


def test_login():
    client.post(
        "/api/v1/user/register",
        json={
            "name": "Maria Silva",
            "email": "maria@example.com",
            "password": "Senha@123",
        },
    )

    response = client.post(
        "/api/v1/user/login",
        json={
            "email": "maria@example.com",
            "password": "Senha@123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    client.post(
        "/api/v1/user/register",
        json={
            "name": "Maria Silva",
            "email": "maria@example.com",
            "password": "Senha@123",
        },
    )

    response = client.post(
        "/api/v1/user/login",
        json={
            "email": "maria@example.com",
            "password": "SenhaErrada",
        },
    )

    assert response.status_code == 401


def test_google_login_creates_user_and_returns_tokens(monkeypatch):
    class FakeGoogleIdentity:
        sub = "google-user-123"
        email = "google-user@example.com"
        name = "Google User"

    monkeypatch.setattr(
        "app.api.v1.endpoints.login.verify_google_credential",
        lambda _: FakeGoogleIdentity(),
    )

    response = client.post(
        "/api/v1/user/google",
        json={"credential": "google-id-token"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]

    me_response = client.get(
        "/api/v1/user/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "google-user@example.com"


def test_google_client_id_uses_vite_fallback(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(settings, "VITE_GOOGLE_CLIENT_ID", "vite-google-client-id")

    assert settings.google_client_id == "vite-google-client-id"


def test_get_my_profile():
    token = create_logged_user()

    response = client.get(
        "/api/v1/user/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "maria@example.com"
    assert response.json()["created_at"] is not None


def test_protected_route_without_token():
    response = client.get("/api/v1/user/me")

    assert response.status_code == 401


def test_update_my_profile():
    token = create_logged_user()

    response = client.put(
        "/api/v1/user/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Maria Souza",
            "phone": "61999999999",
            "cpf": "12345678901",
            "gender": "feminino",
            "birth_date": "1995-05-10",
            "accepts_marketing": True,
        },
    )

    assert response.status_code == 200

    profile_response = client.get(
        "/api/v1/user/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    profile = profile_response.json()
    assert profile["name"] == "Maria Souza"
    assert profile["phone"] == "61999999999"
    assert profile["accepts_marketing"] is True


def test_delete_my_account_anonymizes_user_and_blocks_old_login():
    email = "maria@example.com"
    token = create_logged_user(email=email)

    response = client.request(
        "DELETE",
        "/api/v1/user/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "Senha@123",
            "confirm_email": email,
            "confirm_text": "DELETE",
        },
    )

    assert response.status_code == 200
    assert response.json()["mensagem"] == "Conta excluida com sucesso"

    old_token_response = client.get(
        "/api/v1/user/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert old_token_response.status_code == 401

    login_response = client.post(
        "/api/v1/user/login",
        json={
            "email": email,
            "password": "Senha@123",
        },
    )
    assert login_response.status_code == 401

    register_response = client.post(
        "/api/v1/user/register",
        json={
            "name": "Maria Silva",
            "email": email,
            "password": "NovaSenha@123",
        },
    )
    assert register_response.status_code == 201

    with Session(engine) as session:
        deleted_user = session.exec(
            select(UserInDB).where(UserInDB.disabled == True)  # noqa: E712
        ).one()

    assert deleted_user.deleted_at is not None
    assert deleted_user.email != email
    assert deleted_user.name == "Conta excluida"
    assert deleted_user.cpf is None
    assert deleted_user.phone is None
    assert deleted_user.accepts_marketing is False


def test_delete_my_account_requires_matching_confirmation():
    token = create_logged_user()
    headers = {"Authorization": f"Bearer {token}"}

    wrong_email_response = client.request(
        "DELETE",
        "/api/v1/user/me",
        headers=headers,
        json={
            "current_password": "Senha@123",
            "confirm_email": "outra@example.com",
            "confirm_text": "DELETE",
        },
    )
    assert wrong_email_response.status_code == 400

    wrong_text_response = client.request(
        "DELETE",
        "/api/v1/user/me",
        headers=headers,
        json={
            "current_password": "Senha@123",
            "confirm_email": "maria@example.com",
            "confirm_text": "EXCLUIR",
        },
    )
    assert wrong_text_response.status_code == 400


def test_delete_my_account_rejects_wrong_password_when_provided():
    token = create_logged_user()

    response = client.request(
        "DELETE",
        "/api/v1/user/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": "SenhaErrada",
            "confirm_email": "maria@example.com",
            "confirm_text": "DELETE",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Senha incorreta"


def test_google_user_can_delete_account_without_password(monkeypatch):
    class FakeGoogleIdentity:
        sub = "google-user-123"
        email = "google-user@example.com"
        name = "Google User"

    monkeypatch.setattr(
        "app.api.v1.endpoints.login.verify_google_credential",
        lambda _: FakeGoogleIdentity(),
    )

    login_response = client.post(
        "/api/v1/user/google",
        json={"credential": "google-id-token"},
    )
    token = login_response.json()["access_token"]

    response = client.request(
        "DELETE",
        "/api/v1/user/me",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "confirm_email": "google-user@example.com",
            "confirm_text": "DELETE",
        },
    )

    assert response.status_code == 200

    old_token_response = client.get(
        "/api/v1/user/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert old_token_response.status_code == 401


def test_manage_addresses_keeps_single_default_shipping_address():
    token = create_logged_user()
    headers = {"Authorization": f"Bearer {token}"}

    first_response = client.post(
        "/api/v1/addresses/",
        headers=headers,
        json={
            "label": "Casa",
            "cep": "70000000",
            "street": "Rua A",
            "number": "10",
            "neighborhood": "Centro",
            "city": "Brasilia",
            "state": "DF",
            "region": "Centro-Oeste",
            "ddd": "61",
            "is_default_shipping": True,
            "is_default_billing": False,
        },
    )
    assert first_response.status_code == 201

    second_response = client.post(
        "/api/v1/addresses/",
        headers=headers,
        json={
            "label": "Trabalho",
            "cep": "71000000",
            "street": "Rua B",
            "number": "20",
            "neighborhood": "Asa Norte",
            "city": "Brasilia",
            "state": "DF",
            "region": "Centro-Oeste",
            "ddd": "61",
            "is_default_shipping": True,
            "is_default_billing": False,
        },
    )
    assert second_response.status_code == 201

    addresses_response = client.get("/api/v1/addresses/", headers=headers)

    assert addresses_response.status_code == 200
    addresses = addresses_response.json()
    default_addresses = [
        address for address in addresses if address["is_default_shipping"]
    ]
    assert len(default_addresses) == 1
    assert default_addresses[0]["label"] == "Trabalho"


def test_manage_payment_methods_without_storing_sensitive_card_data():
    token = create_logged_user()
    headers = {"Authorization": f"Bearer {token}"}

    card_response = client.post(
        "/api/v1/payment-methods/",
        headers=headers,
        json={
            "method_type": "card",
            "label": "Cartao principal",
            "holder_name": "Maria Silva",
            "billing_document": "12345678901",
            "card_brand": "visa",
            "card_last4": "4242",
            "card_exp_month": 12,
            "card_exp_year": 2030,
            "cvv": "123",
            "is_default": True,
        },
    )

    assert card_response.status_code == 201
    card = card_response.json()
    assert card["card_last4"] == "4242"
    assert "cvv" not in card

    pix_response = client.post(
        "/api/v1/payment-methods/",
        headers=headers,
        json={
            "method_type": "pix",
            "label": "Pix",
            "billing_document": "12345678901",
            "is_default": True,
        },
    )
    assert pix_response.status_code == 201

    methods_response = client.get("/api/v1/payment-methods/", headers=headers)

    assert methods_response.status_code == 200
    methods = methods_response.json()
    assert methods[0]["method_type"] == "pix"
    assert len([method for method in methods if method["is_default"]]) == 1


def test_profile_orders_and_reviews_come_from_database():
    token = create_logged_user()
    headers = {"Authorization": f"Bearer {token}"}
    profile = client.get("/api/v1/user/me", headers=headers).json()
    user_id = UUID(profile["id"])
    order_id = uuid4()

    empty_orders_response = client.get("/api/v1/user/me/orders", headers=headers)
    empty_reviews_response = client.get("/api/v1/user/me/reviews", headers=headers)

    assert empty_orders_response.status_code == 200
    assert empty_orders_response.json() == []
    assert empty_reviews_response.status_code == 200
    assert empty_reviews_response.json() == []

    with Session(engine) as session:
        address = Address(
            user_id=user_id,
            label="Casa",
            cep="70000000",
            street="Rua A",
            number="10",
            city="Brasilia",
            state="DF",
        )
        product = Product(slug="batom-real", name="Batom Real", price=49.9)
        payment = Payment(
            order_id=order_id,
            user_id=user_id,
            address_id=address.id,
            payer_email=profile["email"],
            amount=Decimal("99.80"),
            status=PaymentStatus.APPROVED,
        )
        payment_item = PaymentItem(
            product_id=product.id,
            payment_id=payment.id,
            title=product.name,
            product_url="/produto/batom-real",
            unit_price=Decimal("49.90"),
            quantity=2,
        )
        review = ProductReview(
            product_id=product.id,
            user_id=user_id,
            rating=5,
            title="Amei",
            comment="Produto aprovado.",
        )

        session.add(address)
        session.add(product)
        session.add(payment)
        session.add(payment_item)
        session.add(review)
        session.commit()

    orders_response = client.get("/api/v1/user/me/orders", headers=headers)
    reviews_response = client.get("/api/v1/user/me/reviews", headers=headers)

    assert orders_response.status_code == 200
    orders = orders_response.json()
    assert orders[0]["id"] == str(order_id)
    assert orders[0]["items_count"] == 2
    assert orders[0]["items"][0]["title"] == "Batom Real"

    assert reviews_response.status_code == 200
    reviews = reviews_response.json()
    assert reviews[0]["product_name"] == "Batom Real"
    assert reviews[0]["rating"] == 5


def test_admin_dashboard_requires_admin_role():
    token = create_logged_user()

    response = client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_stripe_checkout_uses_database_product_and_returns_checkout_url(monkeypatch):
    token = create_logged_user(email="checkout@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    profile = client.get("/api/v1/user/me", headers=headers).json()
    user_id = UUID(profile["id"])
    captured_items: list[dict] = []
    idempotency_key = str(uuid4())

    class FakeStripeSession:
        id = "cs_test_checkout"
        url = "https://checkout.stripe.com/c/pay/cs_test_checkout"
        client_secret = None

    def fake_create_checkout_session(
        items,
        order_id,
        payer_email=None,
        idempotency_key=None,
    ):
        captured_items.extend(items)
        assert payer_email == "checkout@example.com"
        assert str(order_id)
        assert idempotency_key
        return FakeStripeSession()

    monkeypatch.setattr(
        "app.api.v1.endpoints.stripeCheckout.create_checkout_session",
        fake_create_checkout_session,
    )

    with Session(engine) as session:
        address = Address(
            user_id=user_id,
            label="Casa",
            cep="70000000",
            street="Rua A",
            number="10",
            city="Brasilia",
            state="DF",
        )
        product = Product(slug="batom-real", name="Batom Real", price=49.9)
        session.add(address)
        session.add(product)
        session.flush()
        stock = Stock(product_id=product.id, total_quantity=5)
        session.add(stock)
        session.commit()
        address_id = str(address.id)
        product_id = str(product.id)

    checkout_payload = {
        "address_id": address_id,
        "idempotency_key": idempotency_key,
        "items": [
            {
                "id": product_id,
                "name": "Batom Real",
                "slug": "batom-real",
                "product_url": "/produto/batom-real",
                "unit_price": 1,
                "quantity": 2,
            }
        ],
    }
    response = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json=checkout_payload,
    )

    assert response.status_code == 200
    assert response.json()["checkout_url"] == FakeStripeSession.url
    assert response.json()["session_id"] == FakeStripeSession.id
    assert response.json()["order_id"]
    assert captured_items[0]["unit_price"] == Decimal("49.9")

    with Session(engine) as session:
        payment = session.exec(select(Payment)).one()
        item = session.exec(select(PaymentItem)).one()
        stock = session.exec(select(Stock)).one()
        movement = session.exec(select(StockMovement)).one()

        assert payment.amount == Decimal("99.80")
        assert payment.provider_session_id == FakeStripeSession.id
        assert item.product_id == UUID(product_id)
        assert item.unit_price == Decimal("49.90")
        assert item.quantity == 2
        assert stock.total_quantity == 3
        assert movement.movement_type == StockMovementType.OUT
        assert movement.quantity == 2
        assert movement.order_id == payment.order_id

    monkeypatch.setattr(
        "app.api.v1.endpoints.stripeCheckout.retrieve_checkout_session",
        lambda session_id: FakeStripeSession(),
    )
    duplicate_response = client.post(
        "/api/v1/payments/checkout",
        headers=headers,
        json=checkout_payload,
    )

    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["session_id"] == FakeStripeSession.id
    with Session(engine) as session:
        assert len(session.exec(select(Payment)).all()) == 1
        assert len(session.exec(select(StockMovement)).all()) == 1
        assert session.exec(select(Stock)).one().total_quantity == 3


def test_expired_stripe_checkout_releases_stock_only_once(monkeypatch):
    token = create_logged_user(email="expired-checkout@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    profile = client.get("/api/v1/user/me", headers=headers).json()
    user_id = UUID(profile["id"])
    order_id = uuid4()
    stripe_session_id = "cs_test_expired"

    with Session(engine) as session:
        address = Address(
            user_id=user_id,
            label="Casa",
            cep="70000000",
            street="Rua B",
            number="20",
            city="Brasilia",
            state="DF",
        )
        product = Product(slug="perfume-real", name="Perfume Real", price=100)
        session.add(address)
        session.add(product)
        session.flush()

        stock = Stock(product_id=product.id, total_quantity=3)
        payment = Payment(
            order_id=order_id,
            idempotency_key=uuid4(),
            user_id=user_id,
            address_id=address.id,
            payer_email=profile["email"],
            amount=Decimal("200.00"),
            provider_session_id=stripe_session_id,
            status=PaymentStatus.PENDING.value,
        )
        session.add(stock)
        session.add(payment)
        session.flush()
        session.add(
            PaymentItem(
                product_id=product.id,
                payment_id=payment.id,
                title=product.name,
                product_url=f"/produto/{product.slug}",
                unit_price=Decimal("100.00"),
                quantity=2,
            )
        )
        session.add(
            StockMovement(
                product_id=product.id,
                stock_id=stock.id,
                movement_type=StockMovementType.OUT,
                quantity=2,
                reason="Reserva de estoque para checkout Stripe",
                order_id=order_id,
            )
        )
        session.commit()

    pending_response = client.get(
        f"/api/v1/payments/checkout/{stripe_session_id}",
        headers=headers,
    )
    assert pending_response.status_code == 200
    assert pending_response.json()["status"] == PaymentStatus.PENDING.value

    event = {
        "type": "checkout.session.expired",
        "data": {
            "object": {
                "id": stripe_session_id,
                "metadata": {"order_id": str(order_id)},
                "payment_intent": None,
            }
        },
    }
    monkeypatch.setattr(
        "app.api.v1.endpoints.weebhook.stripe.Webhook.construct_event",
        lambda **kwargs: event,
    )

    first_webhook = client.post(
        "/api/v1/payments/webhook",
        content=b"{}",
        headers={"stripe-signature": "test-signature"},
    )
    duplicate_webhook = client.post(
        "/api/v1/payments/webhook",
        content=b"{}",
        headers={"stripe-signature": "test-signature"},
    )

    assert first_webhook.status_code == 200
    assert first_webhook.json()["payment_status"] == PaymentStatus.CANCELLED.value
    assert duplicate_webhook.status_code == 200
    assert duplicate_webhook.json()["duplicate"] is True

    with Session(engine) as session:
        payment = session.exec(select(Payment)).one()
        stock = session.exec(select(Stock)).one()
        movements = session.exec(select(StockMovement)).all()
        returns = [
            movement
            for movement in movements
            if movement.movement_type == StockMovementType.RETURN
        ]

        assert payment.status == PaymentStatus.CANCELLED.value
        assert stock.total_quantity == 5
        assert len(returns) == 1
        assert returns[0].quantity == 2
        assert returns[0].order_id == order_id

    cancelled_response = client.get(
        f"/api/v1/payments/checkout/{stripe_session_id}",
        headers=headers,
    )
    assert cancelled_response.status_code == 200
    assert cancelled_response.json()["status"] == PaymentStatus.CANCELLED.value


def test_admin_dashboard_comes_from_database():
    customer_token = create_logged_user(email="cliente@example.com")
    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    profile = client.get("/api/v1/user/me", headers=customer_headers).json()
    customer_id = UUID(profile["id"])
    admin_token = create_admin_token()

    with Session(engine) as session:
        disabled_user = UserInDB(
            name="Conta Inativa",
            email="inativa@example.com",
            hashed_password=LoginAndJWT.hashing_password("Senha@123"),
            disabled=True,
        )
        address = Address(
            user_id=customer_id,
            label="Casa",
            cep="70000000",
            street="Rua A",
            number="10",
            city="Brasilia",
            state="DF",
        )
        product = Product(slug="batom-real", name="Batom Real", price=49.9)
        inactive_product = Product(
            slug="produto-inativo",
            name="Produto Inativo",
            price=99.9,
            active=False,
        )
        second_product = Product(slug="gloss-real", name="Gloss Real", price=39.9)
        approved_payment = Payment(
            order_id=uuid4(),
            user_id=customer_id,
            address_id=address.id,
            payer_email=profile["email"],
            amount=Decimal("149.70"),
            status=PaymentStatus.APPROVED,
        )
        pending_payment = Payment(
            order_id=uuid4(),
            user_id=customer_id,
            address_id=address.id,
            payer_email=profile["email"],
            amount=Decimal("39.90"),
            status=PaymentStatus.PENDING,
        )
        refunded_payment = Payment(
            order_id=uuid4(),
            user_id=customer_id,
            address_id=address.id,
            payer_email=profile["email"],
            amount=Decimal("39.90"),
            status=PaymentStatus.REFUNDED,
        )
        approved_item = PaymentItem(
            product_id=product.id,
            payment_id=approved_payment.id,
            title=product.name,
            product_url="/produto/batom-real",
            unit_price=Decimal("49.90"),
            quantity=3,
        )
        pending_item = PaymentItem(
            product_id=second_product.id,
            payment_id=pending_payment.id,
            title=second_product.name,
            product_url="/produto/gloss-real",
            unit_price=Decimal("39.90"),
            quantity=1,
        )
        refunded_item = PaymentItem(
            product_id=second_product.id,
            payment_id=refunded_payment.id,
            title=second_product.name,
            product_url="/produto/gloss-real",
            unit_price=Decimal("39.90"),
            quantity=1,
        )
        low_stock = Stock(product_id=product.id, total_quantity=4)
        regular_stock = Stock(product_id=second_product.id, total_quantity=12)

        session.add(disabled_user)
        session.add(address)
        session.add(product)
        session.add(inactive_product)
        session.add(second_product)
        session.add(approved_payment)
        session.add(pending_payment)
        session.add(refunded_payment)
        session.add(approved_item)
        session.add(pending_item)
        session.add(refunded_item)
        session.add(low_stock)
        session.add(regular_stock)
        session.commit()
        top_product_id = str(product.id)

    response = client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    kpis = {kpi["key"]: kpi for kpi in data["kpis"]}
    assert kpis["customers"]["value"] == "1"
    assert kpis["products"]["value"] == "2"
    assert kpis["orders"]["value"] == "3"
    assert kpis["net_sales"]["value"] == "R$ 109,80"
    assert kpis["average_order_value"]["value"] == "R$ 149,70"
    assert kpis["items_sold"]["value"] == "3"
    assert kpis["products"]["detail"] == "1 com estoque baixo"

    overview = data["sales_overview"]
    assert overview["gross_sales"] == 149.7
    assert overview["net_sales"] == 109.8
    assert overview["refunded_sales"] == 39.9
    assert overview["average_order_value"] == 149.7
    assert overview["total_orders"] == 3
    assert overview["paid_orders"] == 1
    assert overview["refunded_orders"] == 1
    assert overview["pending_orders"] == 1
    assert overview["items_sold"] == 3

    assert any(
        month["current_year"] == 149.7 and month["refunded_total"] == 39.9
        for month in data["monthly_revenue"]
    )

    statuses = {item["status"]: item for item in data["status_distribution"]}
    assert statuses["approved"]["count"] == 1
    assert statuses["pending"]["count"] == 1
    assert statuses["refunded"]["count"] == 1
    assert statuses["approved"]["amount"] == 149.7

    recent_statuses = {order["status"] for order in data["recent_orders"]}
    assert recent_statuses == {"approved", "pending", "refunded"}
    assert all(order["customer"] == "Maria Silva" for order in data["recent_orders"])
    assert all(order["customer_email"] == profile["email"] for order in data["recent_orders"])

    assert len(data["top_products"]) == 1
    top_product = data["top_products"][0]
    assert top_product["product_id"] == top_product_id
    assert top_product["name"] == "Batom Real"
    assert top_product["slug"] == "batom-real"
    assert top_product["quantity"] == 3
    assert top_product["orders_count"] == 1
    assert top_product["revenue"] == 149.7
    assert top_product["average_unit_price"] == 49.9
    assert top_product["percent"] == 100
    assert top_product["last_sale_at"] is not None
