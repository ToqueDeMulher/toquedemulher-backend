import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError

from app.core.settings import settings
from app.schemas.create_checkout import CheckoutItem
from app.schemas.products import ProductRequest
from app.services import brasil_api
from app.services import google_identity_service as google


@pytest.mark.parametrize("quantity", [0, -1, 101, 1.5])
def test_checkout_rejects_invalid_quantities(quantity):
    with pytest.raises(ValidationError):
        CheckoutItem(id="fixture", quantity=quantity)


@pytest.mark.parametrize("price", [-1, float("nan"), float("inf"), -float("inf")])
def test_product_rejects_invalid_money(price):
    with pytest.raises(ValidationError):
        ProductRequest(name="Fixture", price=price)


@pytest.fixture
def google_payload(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "fixture-client")
    payload = {
        "iss": "https://accounts.google.com",
        "exp": int(time.time()) + 3600,
        "sub": "fixture-subject",
        "email": "fixture@example.com",
        "email_verified": True,
        "name": "Cliente",
    }
    monkeypatch.setattr(
        google,
        "_get_jwk_client",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key="fixture-key")
        ),
    )

    def decode(token, key, **kwargs):
        assert kwargs == {"algorithms": ["RS256"], "audience": "fixture-client"}
        return payload

    monkeypatch.setattr(google.jwt, "decode", decode)
    return payload


def test_google_accepts_verified_identity_and_preserves_subject(google_payload):
    identity = google.verify_google_credential("fixture-token")
    assert identity.sub == "fixture-subject"
    assert identity.email == "fixture@example.com"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("iss", "https://evil.example"),
        ("exp", 0),
        ("exp", None),
        ("email_verified", False),
        ("sub", ""),
        ("email", ""),
    ],
)
def test_google_rejects_untrusted_claims(google_payload, field, value):
    google_payload[field] = value
    with pytest.raises(HTTPException) as rejected:
        google.verify_google_credential("fixture-token")
    assert rejected.value.status_code == 401


def test_google_rejects_invalid_signature(monkeypatch, google_payload):
    def decode(*args, **kwargs):
        raise InvalidTokenError()

    monkeypatch.setattr(google.jwt, "decode", decode)
    with pytest.raises(HTTPException) as rejected:
        google.verify_google_credential("fixture-token")
    assert rejected.value.status_code == 401


@pytest.mark.parametrize(
    ("status", "expected"), [(404, 404), (429, 503), (500, 503), (503, 503)]
)
def test_brasilapi_failure_uses_safe_message(monkeypatch, status, expected):
    brasil_api._cache.clear()

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["timeout"] == 5.0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, **kwargs):
            return httpx.Response(
                status, json={"error": "dummy"}, request=httpx.Request("GET", url)
            )

    monkeypatch.setattr(brasil_api, "Client", FakeClient)
    with pytest.raises(HTTPException) as rejected:
        brasil_api.lookup_cep("70040010")
    assert rejected.value.status_code == expected
    assert "dummy" not in rejected.value.detail


def test_brasilapi_throttle_expires_and_separates_clients(monkeypatch):
    brasil_api._requests.clear()
    clock = [100.0]
    monkeypatch.setattr(brasil_api, "monotonic", lambda: clock[0])
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))
    for _ in range(30):
        brasil_api.check_rate_limit(request, "cep")
    with pytest.raises(HTTPException) as rejected:
        brasil_api.check_rate_limit(request, "cep")
    assert rejected.value.status_code == 429
    assert rejected.value.headers == {"Retry-After": "60"}
    brasil_api.check_rate_limit(
        SimpleNamespace(client=SimpleNamespace(host="127.0.0.2")), "cep"
    )
    clock[0] += 61
    brasil_api.check_rate_limit(request, "cep")
    brasil_api._requests.clear()
