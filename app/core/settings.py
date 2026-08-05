from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.database_url import (
    DEFAULT_SUPABASE_PROJECT_REF,
    database_engine_options,
    resolve_database_url,
)

# 1. Encontra a pasta raiz do projeto de forma absoluta
# __file__ é este arquivo (settings.py). Vamos subindo as pastas:
# .parent (core) -> .parent (app) -> .parent (Projeto Integrador)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# 2. Junta o caminho da raiz com o nome do arquivo .env
ENV_FILE_PATH = ROOT_DIR / ".env"

class Settings(BaseSettings):
    # 3. Passamos o caminho absoluto (ENV_FILE_PATH) para o Pydantic
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH), 
        env_file_encoding="utf-8",
        extra="ignore"  # Ignora variáveis extras no .env que não estejam listadas aqui
    )

    DATABASE_URL: str = ""
    SQL_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_MODE: str = "queue"

    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str
    FRONTEND_SUCCESS_URL: str
    FRONTEND_PENDING_URL: str
    FRONTEND_FAILURE_URL: str
    SUPABASE_PROJECT_REF: str = DEFAULT_SUPABASE_PROJECT_REF
    SUPABASE_DB_PASSWORD: str = ""
    SUPABASE_DB_USER: str = "postgres"
    SUPABASE_DB_NAME: str = "postgres"
    SUPABASE_DB_HOST: str = ""
    SUPABASE_DB_PORT: int = 5432
    SUPABASE_DB_SSLMODE: str = "require"
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_BUCKET: str = "product-images"
    SUPABASE_FOLDER: str = "products"
    SUPABASE_TIMEOUT: float = 20.0
    PRODUCT_IMAGE_MAX_BYTES: int = 5 * 1024 * 1024
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    @property
    def database_url(self) -> str:
        return resolve_database_url(self)

    @property
    def db_engine_options(self) -> dict[str, object]:
        return database_engine_options(
            self.database_url,
            echo=self.SQL_ECHO,
            pool_size=self.DB_POOL_SIZE,
            max_overflow=self.DB_MAX_OVERFLOW,
            pool_recycle=self.DB_POOL_RECYCLE,
            pool_mode=self.DB_POOL_MODE,
        )


settings = Settings()
