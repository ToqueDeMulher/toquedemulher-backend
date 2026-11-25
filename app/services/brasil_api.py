"""On-demand BrasilAPI lookups: bounded cache, timeout and per-client throttling."""

import hashlib
import ipaddress
import secrets
from collections import OrderedDict, deque
from threading import Lock
from time import monotonic

import httpx
from fastapi import HTTPException
from httpx import Client

_lock = Lock()
_cache = OrderedDict()
_requests = OrderedDict()
CACHE_TTL = 86400
MAX_CACHE_SIZE = 512
RATE_LIMIT = 30
RATE_WINDOW_SECONDS = 60
# Per-process key: buckets hold keyed digests, never raw client addresses.
_BUCKET_KEY = secrets.token_bytes(32)


def client_ip(request):
    """Client address as resolved by the ASGI server, never from raw headers.

    ``X-Forwarded-For`` is honoured only by Uvicorn's ProxyHeadersMiddleware,
    and only when the TCP peer is listed in ``FORWARDED_ALLOW_IPS`` (default
    ``127.0.0.1``). On Vercel the peer is the runtime's local hop and the
    header was overwritten by Vercel's edge, so a client cannot spoof it.
    Reading the header here would let any caller pick its own bucket.
    """
    host = request.client.host if request.client else ""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return None
    if address.version == 6:
        # One IPv6 subscriber usually controls a whole /64.
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


def _bucket(request, category):
    ip = client_ip(request) or "unknown"
    digest = hashlib.blake2b(ip.encode(), key=_BUCKET_KEY, digest_size=16)
    return (digest.hexdigest(), category)


def check_rate_limit(request, category):
    key = _bucket(request, category)
    now = monotonic()
    with _lock:
        queue = _requests.setdefault(key, deque())
        _requests.move_to_end(key)
        while queue and queue[0] <= now - RATE_WINDOW_SECONDS:
            queue.popleft()
        if len(queue) >= RATE_LIMIT:
            raise HTTPException(
                429,
                "Muitas consultas. Aguarde um minuto.",
                headers={"Retry-After": str(RATE_WINDOW_SECONDS)},
            )
        queue.append(now)
        while len(_requests) > 2048:
            _requests.popitem(last=False)


def lookup_cep(cep):
    now = monotonic()
    with _lock:
        cached = _cache.get(cep)
        if cached and cached[0] > now:
            _cache.move_to_end(cep)
            return cached[1]
    try:
        with Client(timeout=5.0) as client:
            response = client.get(
                f"https://brasilapi.com.br/api/cep/v2/{cep}",
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError:
        raise HTTPException(
            503, "Consulta de CEP indisponível. Preencha o endereço manualmente."
        )
    if response.status_code == 404:
        raise HTTPException(
            404, "CEP não encontrado. Confira os dígitos ou preencha manualmente."
        )
    if response.status_code != 200:
        raise HTTPException(
            503, "Consulta de CEP indisponível. Preencha o endereço manualmente."
        )
    try:
        data = response.json()
        result = {
            key: data.get(key) or ""
            for key in ("cep", "state", "city", "neighborhood", "street")
        }
        if result["cep"] != cep or not result["city"] or not result["state"]:
            raise ValueError()
    except (ValueError, AttributeError):
        raise HTTPException(
            502, "A consulta de CEP retornou dados inválidos. Preencha manualmente."
        )
    with _lock:
        _cache[cep] = (now + CACHE_TTL, result)
        _cache.move_to_end(cep)
        while len(_cache) > MAX_CACHE_SIZE:
            _cache.popitem(last=False)
    return result
