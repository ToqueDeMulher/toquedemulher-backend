"""Client identification and per-client throttling behind proxies.

The app never reads X-Forwarded-For itself. These tests run the real FastAPI
app behind Uvicorn's ProxyHeadersMiddleware, the same layer that resolves the
client address in Docker (``uvicorn`` CLI) and on Vercel (the runtime starts a
vendored Uvicorn on 127.0.0.1 and forwards the edge's headers to it).
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.main import app
from app.services import brasil_api

CEP_URL = "/api/v1/brasil/cep/70040010"


@pytest.fixture(autouse=True)
def isolated_limiter(monkeypatch):
    brasil_api._requests.clear()
    brasil_api._cache.clear()
    monkeypatch.setattr(
        brasil_api,
        "lookup_cep",
        lambda cep: {"cep": cep, "state": "DF", "city": "Brasília",
                     "neighborhood": "", "street": ""},
    )
    # The endpoint module imported lookup_cep by name.
    monkeypatch.setattr(
        "app.api.v1.endpoints.brasilApi.lookup_cep", brasil_api.lookup_cep
    )
    yield
    brasil_api._requests.clear()


def server(peer, trusted="127.0.0.1"):
    """Client whose TCP peer is ``peer`` and whose server trusts ``trusted``."""
    return TestClient(
        ProxyHeadersMiddleware(app, trusted_hosts=trusted), client=(peer, 40000)
    )


def exhaust(client, headers=None):
    for _ in range(brasil_api.RATE_LIMIT):
        assert client.get(CEP_URL, headers=headers).status_code == 200


def test_spoofed_forwarded_for_from_untrusted_peer_is_ignored():
    attacker = server("203.0.113.10")
    # Rotating the header must not create fresh buckets.
    for index in range(brasil_api.RATE_LIMIT):
        response = attacker.get(
            CEP_URL, headers={"X-Forwarded-For": f"198.51.100.{index}"}
        )
        assert response.status_code == 200
    blocked = attacker.get(CEP_URL, headers={"X-Forwarded-For": "192.0.2.99"})
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"


def test_app_alone_never_trusts_forwarded_headers():
    direct = TestClient(app, client=("203.0.113.20", 40000))
    for index in range(brasil_api.RATE_LIMIT):
        direct.get(
            CEP_URL,
            headers={"X-Forwarded-For": f"198.51.100.{index}",
                     "X-Real-IP": f"192.0.2.{index}",
                     "X-Vercel-Forwarded-For": f"192.0.2.{index}"},
        )
    assert direct.get(CEP_URL).status_code == 429


def test_trusted_proxy_keeps_different_customers_in_separate_buckets():
    proxy = server("127.0.0.1")  # e.g. Vercel runtime hop or local nginx
    first = {"X-Forwarded-For": "198.51.100.1"}
    second = {"X-Forwarded-For": "198.51.100.2"}
    exhaust(proxy, first)
    assert proxy.get(CEP_URL, headers=first).status_code == 429
    # Another customer behind the same proxy is not affected.
    assert proxy.get(CEP_URL, headers=second).status_code == 200


def test_client_prepended_entries_cannot_escape_the_bucket():
    proxy = server("127.0.0.1")
    for index in range(brasil_api.RATE_LIMIT):
        # The client forges the left entry; the trusted proxy appends the
        # real address on the right. Only the right-most untrusted one counts.
        response = proxy.get(
            CEP_URL, headers={"X-Forwarded-For": f"10.9.9.{index}, 198.51.100.7"}
        )
        assert response.status_code == 200
    blocked = proxy.get(
        CEP_URL, headers={"X-Forwarded-For": "10.9.9.250, 198.51.100.7"}
    )
    assert blocked.status_code == 429


def test_trusted_cidr_from_forwarded_allow_ips():
    proxy = server("10.0.3.4", trusted="10.0.0.0/8")
    exhaust(proxy, {"X-Forwarded-For": "198.51.100.30"})
    assert proxy.get(CEP_URL, headers={"X-Forwarded-For": "198.51.100.31"}).status_code == 200
    untrusted = server("172.16.0.5", trusted="10.0.0.0/8")
    exhaust(untrusted, {"X-Forwarded-For": "198.51.100.40"})
    assert untrusted.get(
        CEP_URL, headers={"X-Forwarded-For": "198.51.100.41"}
    ).status_code == 429


def test_categories_are_independent_and_window_expires(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(brasil_api, "monotonic", lambda: clock[0])
    request = SimpleNamespace(client=SimpleNamespace(host="198.51.100.50"))
    for _ in range(brasil_api.RATE_LIMIT):
        brasil_api.check_rate_limit(request, "quotes")
    with pytest.raises(HTTPException) as rejected:
        brasil_api.check_rate_limit(request, "quotes")
    assert rejected.value.status_code == 429
    brasil_api.check_rate_limit(request, "cep")  # other category still free
    clock[0] += brasil_api.RATE_WINDOW_SECONDS + 1
    brasil_api.check_rate_limit(request, "quotes")


def test_ipv6_addresses_share_their_64_prefix():
    one = SimpleNamespace(client=SimpleNamespace(host="2001:db8:1:2::a"))
    same_prefix = SimpleNamespace(client=SimpleNamespace(host="2001:db8:1:2:ffff::1"))
    other_prefix = SimpleNamespace(client=SimpleNamespace(host="2001:db8:1:3::a"))
    assert brasil_api.client_ip(one) == brasil_api.client_ip(same_prefix)
    assert brasil_api.client_ip(one) != brasil_api.client_ip(other_prefix)
    for _ in range(brasil_api.RATE_LIMIT):
        brasil_api.check_rate_limit(one, "quotes")
    with pytest.raises(HTTPException):
        brasil_api.check_rate_limit(same_prefix, "quotes")
    brasil_api.check_rate_limit(other_prefix, "quotes")


@pytest.mark.parametrize("host", [None, "", "testclient", "not-an-ip"])
def test_unparseable_peer_falls_back_to_shared_unknown_bucket(host):
    client = None if host is None else SimpleNamespace(host=host)
    assert brasil_api.client_ip(SimpleNamespace(client=client)) is None


def test_limiter_memory_holds_no_raw_addresses():
    request = SimpleNamespace(client=SimpleNamespace(host="198.51.100.77"))
    brasil_api.check_rate_limit(request, "quotes")
    stored = repr(list(brasil_api._requests))
    assert "198.51.100.77" not in stored


def test_quote_throttle_stops_before_calling_melhor_envio(monkeypatch):
    from app.services import melhor_envio as me

    calls = []
    monkeypatch.setattr(me, "create_quote", lambda payload, session: calls.append(1) or {})
    proxy = server("127.0.0.1")
    body = {"postal_code": "70040010", "items": [{"id": "x", "quantity": 1}]}
    customer = {"X-Forwarded-For": "198.51.100.90"}
    for _ in range(brasil_api.RATE_LIMIT):
        assert proxy.post("/api/v1/shipping/quotes", json=body, headers=customer).status_code == 200
    response = proxy.post("/api/v1/shipping/quotes", json=body, headers=customer)
    assert response.status_code == 429
    assert len(calls) == brasil_api.RATE_LIMIT
    other = {"X-Forwarded-For": "198.51.100.91"}
    assert proxy.post("/api/v1/shipping/quotes", json=body, headers=other).status_code == 200


def test_uvicorn_trusts_only_loopback_by_default(monkeypatch):
    import uvicorn

    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    assert uvicorn.Config(app).forwarded_allow_ips == "127.0.0.1"
