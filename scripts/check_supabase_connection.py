from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.core.database_url import database_engine_options, resolve_database_url  # noqa: E402


class EnvSettings:
    def __init__(self) -> None:
        self.DATABASE_URL = os.getenv("DATABASE_URL", "")
        self.SUPABASE_PROJECT_REF = os.getenv(
            "SUPABASE_PROJECT_REF", "inugzqvfzgnxbpxfbkqa"
        )
        self.SUPABASE_DB_PASSWORD = os.getenv("SUPABASE_DB_PASSWORD", "")
        self.SUPABASE_DB_USER = os.getenv("SUPABASE_DB_USER", "postgres")
        self.SUPABASE_DB_NAME = os.getenv("SUPABASE_DB_NAME", "postgres")
        self.SUPABASE_DB_HOST = os.getenv("SUPABASE_DB_HOST", "")
        self.SUPABASE_DB_PORT = int(os.getenv("SUPABASE_DB_PORT", "5432"))
        self.SUPABASE_DB_SSLMODE = os.getenv("SUPABASE_DB_SSLMODE", "require")


def main() -> None:
    load_dotenv(ROOT_DIR / ".env")

    settings = EnvSettings()
    database_url = resolve_database_url(settings)
    engine = create_engine(
        database_url,
        **database_engine_options(database_url, pool_size=1, max_overflow=0),
    )

    with engine.connect() as connection:
        row = connection.execute(
            text("select current_database(), current_user, current_schema()")
        ).one()

    print("Conexao com Supabase/Postgres OK")
    print(f"database={row[0]}")
    print(f"user={row[1]}")
    print(f"schema={row[2]}")


if __name__ == "__main__":
    main()
