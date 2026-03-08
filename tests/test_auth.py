"""
Testes de autenticação da API.
Execute com: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.base import Base, get_db

# Banco de dados em memória para testes
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=engine)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Limpa o banco de dados antes de cada teste."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_health_check():
    """Testa o endpoint de health check."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_user():
    """Testa o registro de um novo usuário."""
    response = client.post("/api/v1/auth/register", json={
        "full_name": "Maria Silva",
        "email": "maria@example.com",
        "password": "Senha@123",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "maria@example.com"
    assert data["full_name"] == "Maria Silva"
    assert "hashed_password" not in data


def test_register_duplicate_email():
    """Testa que não é possível registrar dois usuários com o mesmo email."""
    user_data = {"full_name": "Maria Silva", "email": "maria@example.com", "password": "Senha@123"}
    client.post("/api/v1/auth/register", json=user_data)
    response = client.post("/api/v1/auth/register", json=user_data)
    assert response.status_code == 409


def test_login():
    """Testa o login de um usuário."""
    client.post("/api/v1/auth/register", json={
        "full_name": "Maria Silva",
        "email": "maria@example.com",
        "password": "Senha@123",
    })
    response = client.post("/api/v1/auth/login", json={
        "email": "maria@example.com",
        "password": "Senha@123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    """Testa que login com senha errada retorna 401."""
    client.post("/api/v1/auth/register", json={
        "full_name": "Maria Silva",
        "email": "maria@example.com",
        "password": "Senha@123",
    })
    response = client.post("/api/v1/auth/login", json={
        "email": "maria@example.com",
        "password": "SenhaErrada",
    })
    assert response.status_code == 401


def test_get_my_profile():
    """Testa que o usuário pode ver seu próprio perfil."""
    client.post("/api/v1/auth/register", json={
        "full_name": "Maria Silva",
        "email": "maria@example.com",
        "password": "Senha@123",
    })
    login_response = client.post("/api/v1/auth/login", json={
        "email": "maria@example.com",
        "password": "Senha@123",
    })
    token = login_response.json()["access_token"]

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "maria@example.com"


def test_protected_route_without_token():
    """Testa que rotas protegidas retornam 401 sem token."""
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
