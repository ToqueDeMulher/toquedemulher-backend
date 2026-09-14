"""On-demand BrasilAPI lookups: bounded cache, timeout and per-client throttling."""

from collections import OrderedDict, deque
from threading import Lock
from time import monotonic
import httpx
from httpx import Client
from fastapi import HTTPException

_lock = Lock()
_cache = OrderedDict()
_requests = OrderedDict()
CACHE_TTL = 86400
MAX_CACHE_SIZE = 512


def check_rate_limit(request, category):
    key = (request.client.host if request.client else "unknown", category)
    now = monotonic()
    with _lock:
        queue = _requests.setdefault(key, deque())
        _requests.move_to_end(key)
        while queue and queue[0] <= now - 60:
            queue.popleft()
        if len(queue) >= 30:
            raise HTTPException(
                429,
                "Muitas consultas. Aguarde um minuto.",
                headers={"Retry-After": "60"},
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
