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
from app.models.user import UserInDB  # noqa: E402
from app.services.email_confirmation_service import create_email_confirmation_token  # noqa: E402


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


def test_health_check():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
