from contextlib import asynccontextmanager
from pathlib import Path
from math import isfinite

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.db import Database, _SessionDep
from app.core.settings import settings


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.CREATE_TABLES_ON_STARTUP:
        Database.create_db_and_tables()
    yield


app = FastAPI(title="Toque de Mulher API", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_request(request, exc):
    # Validation inputs can include NaN/Infinity, which JSONResponse cannot serialize.
    return JSONResponse(status_code=422, content=jsonable_encoder(
        {'detail': exc.errors()}, custom_encoder={float: lambda v: v if isfinite(v) else None}))


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request, exc):
    return JSONResponse(
        status_code=503,
        content={"detail": "Não foi possível consultar a loja agora. Tente novamente em instantes."},
    )

origins = [
    origin.strip()
    for origin in settings.CORS_ORIGINS.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/ready")
def readiness_check(session: _SessionDep):
    session.exec(text("SELECT 1")).one()
    return {"status": "ready"}


app.include_router(api_router)


# --- TEMPORARY DIAGNOSTIC (branch diag/client-ip only, never merge) ---------
# Shows how the caller's IP reaches the app without exposing or logging it:
# every address is replaced by a keyed fingerprint (HMAC with SECRET_KEY).
import hmac as _hmac
import hashlib as _hashlib
from fastapi import Request as _Request
from fastapi.responses import JSONResponse as _JSONResponse


def _fp(value):
    if not value:
        return None
    return _hmac.new(
        settings.SECRET_KEY.encode(), value.strip().encode(), _hashlib.sha256
    ).hexdigest()[:10]


@app.get("/api/v1/_diag/client-ip", include_in_schema=False)
def _client_ip_diagnostic(request: _Request):
    def header(name):
        raw = request.headers.get(name)
        entries = [item for item in (raw or "").split(",") if item.strip()]
        return {"present": raw is not None, "entries": len(entries),
                "fingerprints": [_fp(item) for item in entries]}

    vercel_id = request.headers.get("x-vercel-id", "")
    body = {
        "rate_limit_key_fingerprint": _fp(request.client.host if request.client else None),
        "x-forwarded-for": header("x-forwarded-for"),
        "x-real-ip": header("x-real-ip"),
        "x-vercel-forwarded-for": header("x-vercel-forwarded-for"),
        "forwarded": header("forwarded"),
        "host": request.headers.get("host"),
        "x-forwarded-host": request.headers.get("x-forwarded-host"),
        "country": request.headers.get("x-vercel-ip-country"),
        "region": request.headers.get("x-vercel-ip-country-region"),
        # Only the region hops (e.g. "gru1::iad1"), not the request id.
        "vercel_hops": "::".join(vercel_id.split("::")[:-1]) or None,
        "has_x_vercel_proxy_signature": "x-vercel-proxy-signature" in request.headers,
    }
    return _JSONResponse(body, headers={"Cache-Control": "no-store"})
