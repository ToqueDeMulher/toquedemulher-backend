from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    SQL_ECHO: bool = False

    CORS_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_BUCKET: str = "product-images"
    SUPABASE_FOLDER: str = "products"
    SUPABASE_TIMEOUT: float = 20.0
    PRODUCT_IMAGE_MAX_BYTES: int = 5 * 1024 * 1024


settings = Settings()
