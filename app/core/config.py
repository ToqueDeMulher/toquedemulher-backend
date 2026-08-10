from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.database_url import (
    DEFAULT_SUPABASE_PROJECT_REF,
    database_engine_options,
    resolve_database_url,
)


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE_PATH = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Aplicacao
    APP_NAME: str = "O Toque de Mulher"
    APP_VERSION: str = "1.0.0"
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Banco de Dados
    DATABASE_URL: str = ""
    SQL_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_MODE: str = "queue"
    SUPABASE_PROJECT_REF: str = DEFAULT_SUPABASE_PROJECT_REF
    SUPABASE_DB_PASSWORD: str = ""
    SUPABASE_DB_USER: str = "postgres"
    SUPABASE_DB_NAME: str = "postgres"
    SUPABASE_DB_HOST: str = ""
    SUPABASE_DB_PORT: int = 5432
    SUPABASE_DB_SSLMODE: str = "require"

    # Redis
    REDIS_URL: str = ""

    # Mercado Pago
    MERCADOPAGO_ACCESS_TOKEN: str = ""
    MERCADOPAGO_PUBLIC_KEY: str = ""
    MERCADOPAGO_WEBHOOK_SECRET: str = ""

    # PagBank
    PAGBANK_TOKEN: str = ""
    PAGBANK_EMAIL: str = ""
    PAGBANK_SANDBOX: bool = True

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@toquedemulher.com.br"
    EMAIL_FROM_NAME: str = "O Toque de Mulher"

    # Upload
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # API
    API_V1_PREFIX: str = "/api/v1"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

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
