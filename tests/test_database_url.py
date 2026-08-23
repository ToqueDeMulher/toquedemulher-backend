from app.core.database_url import (
    build_supabase_database_url,
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
