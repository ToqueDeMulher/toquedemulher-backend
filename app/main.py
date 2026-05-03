from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.db import Database
from app.core.settings import settings
from app.api.v1.endpoints.product import router as product
from app.api.v1.endpoints.stripeCheckout import router as payments_router
from app.api.v1.endpoints.user import router as crateUser
from app.api.v1.endpoints.weebhook import router as weebhook
from app.api.v1.endpoints.login import router as login
from app.api.v1.endpoints.addressRouter import router as address
from app.api.v1.endpoints.supplier import router as supplier
from app.api.v1.endpoints.stock import router as stock
from app.api.v1.endpoints.supplierProduct import router as supplierProduct




app = FastAPI(title="Toque de Mulher API")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # ou ["*"] so pra testar
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def on_startup():
    Database.create_db_and_tables()


app.include_router(product)
app.include_router(payments_router)
app.include_router(crateUser)
app.include_router(weebhook)
app.include_router(login)
app.include_router(address)
app.include_router(stock)
app.include_router(supplier)
app.include_router(supplierProduct)