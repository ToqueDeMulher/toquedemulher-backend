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
        self.DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))


def connection_error_hint(error: Exception) -> str:
    """Classify driver errors without returning connection strings or credentials."""
    message = str(getattr(error, "orig", error)).lower()
    if "eauthquery" in message or "ecircuitbreaker" in message:
        return (
            "O pooler nao conseguiu autenticar a conexao com o Postgres. "
            "Confira o estado do projeto, os logs e a connection string no painel Supabase."
        )
    if "password authentication failed" in message:
        return "A autenticacao foi recusada. Confira usuario e senha na connection string."
    if "tenant or user not found" in message:
        return "Confira o host do pooler e o usuario com o identificador do projeto."
    if "could not translate host name" in message or "name or service not known" in message:
        return "O host do banco nao foi resolvido. Confira DNS, endpoint e estado do projeto."
    if "timeout" in message or "timed out" in message:
        return (
            "A conexao expirou. Confira rede, porta, restricoes de acesso "
            "e o endpoint atual no painel Supabase."
        )
    return "Confira a configuracao da conexao e as permissoes no painel Supabase."


def main() -> int:
    load_dotenv(ROOT_DIR / ".env")

    engine = None
    try:
        settings = EnvSettings()
        database_url = resolve_database_url(settings)
        if not database_url.startswith("postgresql"):
            print("Este diagnostico exige uma conexao PostgreSQL/Supabase.", file=sys.stderr)
            return 2
        engine = create_engine(
            database_url,
            **database_engine_options(
                database_url, pool_mode="null", connect_timeout=settings.DB_CONNECT_TIMEOUT
            ),
        )

        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text("SET TRANSACTION READ ONLY"))
                row = connection.execute(
                    text("select current_database(), current_user, current_schema()")
                ).one()

        print("Conexao com Supabase/Postgres OK")
        print(f"database={row[0]}")
        print(f"user={row[1]}")
        print(f"schema={row[2]}")
        return 0
    except Exception as error:
        print(f"Falha na conexao ({type(error).__name__}). {connection_error_hint(error)}",
              file=sys.stderr)
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
