import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import NullPool, QueuePool

from app.core.database_url import (
    build_supabase_database_url,
    database_engine_options,
    normalize_database_url,
    resolve_database_url,
)


class SettingsStub:
    DATABASE_URL = ""
    SUPABASE_PROJECT_REF = "inugzqvfzgnxbpxfbkqa"
    SUPABASE_DB_PASSWORD = "p@ss/word"
    SUPABASE_DB_USER = "postgres"
    SUPABASE_DB_NAME = "postgres"
    SUPABASE_DB_HOST = ""
    SUPABASE_DB_PORT = 5432
    SUPABASE_DB_SSLMODE = "require"


def test_normalize_database_url_converts_postgres_scheme_and_adds_sslmode():
    url = normalize_database_url(
        "postgres://postgres:secret@db.example.supabase.co:5432/postgres"
    )

    assert url == (
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres"
        "?sslmode=require"
    )


def test_normalize_database_url_preserves_existing_sslmode():
    url = normalize_database_url(
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres"
        "?sslmode=verify-full"
    )

    assert url.endswith("sslmode=verify-full")


def test_build_supabase_database_url_escapes_password():
    url = build_supabase_database_url(
        project_ref="inugzqvfzgnxbpxfbkqa",
        db_password="p@ss/word",
    )

    assert url == (
        "postgresql+psycopg2://postgres:p%40ss%2Fword@"
        "db.inugzqvfzgnxbpxfbkqa.supabase.co:5432/postgres?sslmode=require"
    )


def test_resolve_database_url_prefers_explicit_database_url():
    settings = SettingsStub()
    settings.DATABASE_URL = "postgres://postgres:secret@db.example.supabase.co/postgres"

    assert resolve_database_url(settings) == (
        "postgresql://postgres:secret@db.example.supabase.co/postgres"
        "?sslmode=require"
    )


def test_resolve_database_url_builds_from_supabase_settings():
    assert resolve_database_url(SettingsStub()) == (
        "postgresql+psycopg2://postgres:p%40ss%2Fword@"
        "db.inugzqvfzgnxbpxfbkqa.supabase.co:5432/postgres?sslmode=require"
    )


@pytest.mark.parametrize(
    "host,port,mode,serverless,expected_pool",
    [
        ("db.example.supabase.co", 5432, "auto", False, QueuePool),
        ("aws-0-ca-central-1.pooler.supabase.com", 5432, "auto", False, QueuePool),
        ("aws-0-ca-central-1.pooler.supabase.com", 6543, "auto", False, NullPool),
        ("db.example.supabase.co", 5432, "auto", True, NullPool),
        ("aws-0-ca-central-1.pooler.supabase.com", 5432, "auto", True, NullPool),
        ("db.example.supabase.co", 5432, "null", False, NullPool),
        ("db.example.supabase.co", 5432, "queue", True, QueuePool),
    ],
)
def test_engine_uses_pool_for_connection_lifecycle(host, port, mode, serverless, expected_pool):
    url = f"postgresql://postgres:secret@{host}:{port}/postgres"
    engine = create_engine(url, **database_engine_options(
        url, pool_mode=mode, serverless=serverless, pool_timeout=4))
    try:
        assert isinstance(engine.pool, expected_pool)
        if isinstance(engine.pool, QueuePool):
            assert engine.pool.timeout() == 4
    finally:
        engine.dispose()


def test_postgres_connect_timeout_reaches_driver_without_network():
    url = "postgresql://postgres:secret@db.example.supabase.co/postgres"
    engine = create_engine(url, **database_engine_options(url, connect_timeout=3))
    captured = {}

    class StopBeforeNetwork(Exception):
        pass

    @event.listens_for(engine, "do_connect")
    def capture_connection(dialect, record, args, params):
        captured.update(params)
        raise StopBeforeNetwork

    try:
        with pytest.raises(StopBeforeNetwork):
            engine.connect()
        assert captured["connect_timeout"] == 3
    finally:
        engine.dispose()


def test_vercel_environment_selects_null_pool(monkeypatch):
    from app.core.settings import Settings

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("DB_POOL_MODE", raising=False)
    settings = Settings(_env_file=None, SECRET_KEY="test-secret",
                        DATABASE_URL="postgresql://postgres:secret@db.example.supabase.co/postgres")
    engine = create_engine(settings.database_url, **settings.db_engine_options)
    try:
        assert isinstance(engine.pool, NullPool)
    finally:
        engine.dispose()


def test_sqlite_still_executes_queries_with_default_options():
    engine = create_engine("sqlite://", **database_engine_options("sqlite://"))
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1")) == 1
    finally:
        engine.dispose()


@pytest.mark.parametrize("options", [
    {"pool_mode": "invalid"}, {"connect_timeout": 0}, {"pool_timeout": 0},
])
def test_invalid_connection_options_fail_before_connecting(options):
    with pytest.raises(ValueError):
        database_engine_options("postgresql://postgres:secret@localhost/postgres", **options)
