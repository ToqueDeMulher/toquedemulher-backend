from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse


DEFAULT_SUPABASE_PROJECT_REF = "inugzqvfzgnxbpxfbkqa"


def normalize_database_url(database_url: str, *, sslmode: str = "require") -> str:
    """Return a SQLAlchemy-compatible Postgres URL with SSL enabled by default."""
    url = database_url.strip()
    if not url:
        return ""

    if url.startswith("postgres://"):
        url = f"postgresql://{url.removeprefix('postgres://')}"

    parsed = urlparse(url)
    if parsed.scheme.startswith("postgresql") and "sslmode=" not in parsed.query:
        query = parse_qsl(parsed.query, keep_blank_values=True)
        query.append(("sslmode", sslmode))
        url = urlunparse(parsed._replace(query=urlencode(query)))

    return url


def build_supabase_database_url(
    *,
    project_ref: str,
    db_password: str,
    db_user: str = "postgres",
    db_name: str = "postgres",
    db_host: str = "",
    db_port: int = 5432,
    sslmode: str = "require",
) -> str:
    if not project_ref or not db_password:
        return ""

    host = db_host or f"db.{project_ref}.supabase.co"
    user = quote(db_user, safe="")
    password = quote(db_password, safe="")
    database = quote(db_name, safe="")
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{db_port}/{database}"

    return normalize_database_url(url, sslmode=sslmode)


def resolve_database_url(settings: Any) -> str:
    explicit_url = getattr(settings, "DATABASE_URL", "") or ""
    sslmode = getattr(settings, "SUPABASE_DB_SSLMODE", "require") or "require"
    if explicit_url.strip():
        return normalize_database_url(explicit_url, sslmode=sslmode)

    supabase_url = build_supabase_database_url(
        project_ref=getattr(settings, "SUPABASE_PROJECT_REF", "") or "",
        db_password=getattr(settings, "SUPABASE_DB_PASSWORD", "") or "",
        db_user=getattr(settings, "SUPABASE_DB_USER", "postgres") or "postgres",
        db_name=getattr(settings, "SUPABASE_DB_NAME", "postgres") or "postgres",
        db_host=getattr(settings, "SUPABASE_DB_HOST", "") or "",
        db_port=getattr(settings, "SUPABASE_DB_PORT", 5432) or 5432,
        sslmode=sslmode,
    )
    if supabase_url:
        return supabase_url

    raise RuntimeError(
        "Defina DATABASE_URL ou SUPABASE_PROJECT_REF + SUPABASE_DB_PASSWORD no .env."
    )


def database_engine_options(
    database_url: str,
    *,
    echo: bool = False,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_recycle: int = 1800,
    pool_mode: str = "queue",
) -> dict[str, Any]:
    options: dict[str, Any] = {"echo": echo}

    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
        return options

    if pool_mode.lower() == "null":
        from sqlalchemy.pool import NullPool

        options["poolclass"] = NullPool
        options["pool_pre_ping"] = True
        return options

    options.update(
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
    )
    return options
