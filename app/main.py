from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.api.v1.router import api_router
from app.db.base import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Executa tarefas na inicialização e encerramento da aplicação."""
    # Criar tabelas no banco de dados (em produção, usar Alembic)
    Base.metadata.create_all(bind=engine)
    # Criar diretório de uploads
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API backend completa para o e-commerce de beleza e perfumes "
        "'O Toque de Mulher'. Inclui autenticação JWT, gestão de produtos, "
        "carrinho, pedidos, pagamentos via Mercado Pago e avaliações."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── Middlewares ──────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Rotas ───────────────────────────────────────────────────────────────────

app.include_router(api_router)

# Servir arquivos estáticos (uploads de imagens)
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["Sistema"])
def health_check():
    """Verifica se a API está funcionando corretamente."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
