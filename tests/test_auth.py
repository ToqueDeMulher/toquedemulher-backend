"""
Testes de autenticacao da API ativa.
Execute com: pytest tests/ -v
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("FRONTEND_SUCCESS_URL", "http://localhost/success")
os.environ.setdefault("FRONTEND_PENDING_URL", "http://localhost/pending")
os.environ.setdefault("FRONTEND_FAILURE_URL", "http://localhost/failure")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test")

from app.core.db import Database  # noqa: E402
from app.main import app  # noqa: E402


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
    assert response.json()["mensagem"] == "Usuario criado com sucesso"


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


def test_get_my_profile():
    client.post(
        "/api/v1/user/register",
        json={
            "name": "Maria Silva",
            "email": "maria@example.com",
            "password": "Senha@123",
        },
    )
    login_response = client.post(
        "/api/v1/user/login",
        json={
            "email": "maria@example.com",
            "password": "Senha@123",
        },
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/user/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "maria@example.com"


def test_protected_route_without_token():
    response = client.get("/api/v1/user/me")

    assert response.status_code == 401
