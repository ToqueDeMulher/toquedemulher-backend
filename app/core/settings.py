from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    DATABASE_URL: str
    SQL_ECHO: bool = False

    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    MERCADO_PAGO_ACCESS_TOKEN: str
    MERCADO_PAGO_PUBLIC_KEY: str
    MERCADO_PAGO_WEBHOOK_URL: str
    FRONTEND_SUCCESS_URL: str
    FRONTEND_PENDING_URL: str
    FRONTEND_FAILURE_URL: str
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_BUCKET: str = "product-images"
    SUPABASE_FOLDER: str = "products"
    SUPABASE_TIMEOUT: float = 20.0
    PRODUCT_IMAGE_MAX_BYTES: int = 5 * 1024 * 1024


settings = Settings()