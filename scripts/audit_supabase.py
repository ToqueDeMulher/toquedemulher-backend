"""Compare the live Supabase schema with the backend without modifying it.

Use --export-sql to prepare a SQL Editor diagnostic without database credentials.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import CheckConstraint, Enum, create_engine, text
from sqlalchemy.dialects import postgresql
from sqlmodel import SQLModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.models  # noqa: E402, F401
from app.core.database_url import resolve_database_url  # noqa: E402
from scripts.check_supabase_connection import EnvSettings  # noqa: E402


def sql_literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def expected_objects() -> list[dict[str, str]]:
    objects = []
    dialect = postgresql.dialect()
    for table in SQLModel.metadata.sorted_tables:
        objects.append(dict(kind="table", table_name=table.name, name="", detail=""))
        for column in table.columns:
            objects.append(dict(
                kind="column", table_name=table.name, name=column.name,
                detail=json.dumps({"type": str(column.type.compile(dialect=dialect)),
                                   "nullable": column.nullable}),
            ))
            if isinstance(column.type, Enum):
                for label in column.type.enums:
                    objects.append(dict(kind="enum", table_name="", name=column.type.name,
                                        detail=label))
        for index in table.indexes:
            objects.append(dict(
                kind="index", table_name=table.name, name=index.name,
                detail=json.dumps({"columns": [c.name for c in index.columns],
                                   "unique": index.unique,
                                   "predicate": str(index.dialect_options["postgresql"]["where"])
                                       if index.dialect_options["postgresql"]["where"] is not None else None}),
            ))
        objects.append(dict(kind="primary_key", table_name=table.name, name="",
                            detail=json.dumps([c.name for c in table.primary_key.columns])))
        for constraint in table.foreign_key_constraints:
            objects.append(dict(
                kind="foreign_key", table_name=table.name, name="",
                detail=json.dumps({"columns": [e.parent.name for e in constraint.elements],
                                   "target_table": constraint.elements[0].column.table.name,
                                   "target_columns": [e.column.name for e in constraint.elements]}),
            ))
        for constraint in table.constraints:
            if isinstance(constraint, CheckConstraint) and constraint.name:
                objects.append(dict(kind="check", table_name=table.name,
                                    name=constraint.name, detail=""))
    return objects


def diagnostic_sql() -> str:
    payload = sql_literal(json.dumps(expected_objects()))
    return f"""-- Read-only schema audit generated from the current backend models.
-- An empty result means the objects checked here match; it does not certify data health.
-- Check constraints are checked by name, not by logical equivalence of their expressions.
WITH expected AS (
    SELECT * FROM json_to_recordset({payload}::json)
        AS e(kind text, table_name text, name text, detail text)
), tables AS (
    SELECT c.oid, c.relname AS name, c.relrowsecurity AS rls
    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
), columns AS (
    SELECT t.name AS table_name, a.attname AS name, a.attnotnull,
           format_type(a.atttypid, a.atttypmod) AS type
    FROM tables t JOIN pg_attribute a ON a.attrelid = t.oid
    WHERE a.attnum > 0 AND NOT a.attisdropped
), constraints AS (
    SELECT t.name AS table_name, c.conname AS name, c.contype, c.convalidated AS validated,
           to_jsonb(ARRAY(SELECT a.attname::text FROM unnest(c.conkey)
                         WITH ORDINALITY k(num, pos)
                         JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.num
                         ORDER BY k.pos)) AS columns,
           target.relname AS target_table, ns.nspname AS target_schema,
           to_jsonb(ARRAY(SELECT a.attname::text FROM unnest(c.confkey)
                         WITH ORDINALITY k(num, pos)
                         JOIN pg_attribute a ON a.attrelid = c.confrelid AND a.attnum = k.num
                         ORDER BY k.pos)) AS target_columns
    FROM tables t JOIN pg_constraint c ON c.conrelid = t.oid
    LEFT JOIN pg_class target ON target.oid = c.confrelid
    LEFT JOIN pg_namespace ns ON ns.oid = target.relnamespace
), indexes AS (
    SELECT t.name AS table_name, idx.relname AS name, i.indisunique, i.indisvalid,
           pg_get_expr(i.indpred, i.indrelid) AS predicate,
           to_jsonb(ARRAY(SELECT a.attname::text FROM unnest(i.indkey::smallint[])
                         WITH ORDINALITY k(num, pos)
                         JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.num
                         WHERE k.pos <= i.indnkeyatts ORDER BY k.pos)) AS columns
    FROM tables t JOIN pg_index i ON i.indrelid = t.oid
    JOIN pg_class idx ON idx.oid = i.indexrelid
), findings AS (
    SELECT 'missing_table' AS issue, e.table_name, e.name, e.detail
    FROM expected e WHERE e.kind = 'table'
      AND NOT EXISTS (SELECT 1 FROM tables t WHERE t.name = e.table_name)
    UNION ALL
    SELECT 'unexpected_public_table', t.name, '', ''
    FROM tables t WHERE NOT EXISTS (
        SELECT 1 FROM expected e WHERE e.kind = 'table' AND e.table_name = t.name)
    UNION ALL
    SELECT 'unvalidated_constraint', c.table_name, c.name, ''
    FROM constraints c WHERE c.contype IN ('c', 'f') AND NOT c.validated
    UNION ALL
    SELECT 'rls_disabled', e.table_name, e.name, e.detail
    FROM expected e JOIN tables t ON t.name = e.table_name
    WHERE e.kind = 'table' AND NOT t.rls
    UNION ALL
    SELECT 'missing_column', e.table_name, e.name, e.detail
    FROM expected e JOIN tables t ON t.name = e.table_name
    WHERE e.kind = 'column' AND NOT EXISTS (
        SELECT 1 FROM columns c WHERE c.table_name = e.table_name AND c.name = e.name)
    UNION ALL
    SELECT 'column_type_mismatch', e.table_name, e.name, 'expected=' ||
           (e.detail::jsonb->>'type') || ', actual=' || c.type
    FROM expected e JOIN columns c ON c.table_name = e.table_name AND c.name = e.name
    WHERE e.kind = 'column' AND
      regexp_replace(replace(replace(lower(e.detail::jsonb->>'type'), 'float', 'double precision'),
                             'varchar', 'character varying'), '\\s|\\([0-9]+\\)$', '', 'g')
      <> regexp_replace(c.type, '\\s|\\([0-9]+\\)$', '', 'g')
    UNION ALL
    SELECT 'column_nullability_mismatch', e.table_name, e.name, e.detail
    FROM expected e JOIN columns c ON c.table_name = e.table_name AND c.name = e.name
    WHERE e.kind = 'column' AND (e.detail::jsonb->>'nullable')::boolean = c.attnotnull
    UNION ALL
    SELECT 'missing_enum_value', e.table_name, e.name, e.detail
    FROM expected e WHERE e.kind = 'enum' AND NOT EXISTS (
        SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_enum v ON v.enumtypid = t.oid
        WHERE n.nspname = 'public' AND t.typname = e.name AND v.enumlabel = e.detail)
    UNION ALL
    SELECT 'missing_or_incompatible_index', e.table_name, e.name, e.detail
    FROM expected e JOIN tables t ON t.name = e.table_name
    WHERE e.kind = 'index' AND NOT EXISTS (
        SELECT 1 FROM indexes i WHERE i.table_name = e.table_name AND i.indisvalid
          AND i.columns = e.detail::jsonb->'columns'
          AND regexp_replace(lower(coalesce(i.predicate, '')), '\\s|[()]', '', 'g')
              = regexp_replace(lower(coalesce(e.detail::jsonb->>'predicate', '')), '\\s|[()]', '', 'g')
          AND (NOT (e.detail::jsonb->>'unique')::boolean OR i.indisunique))
    UNION ALL
    SELECT 'missing_primary_key', e.table_name, e.name, e.detail
    FROM expected e JOIN tables t ON t.name = e.table_name
    WHERE e.kind = 'primary_key' AND NOT EXISTS (
        SELECT 1 FROM constraints c WHERE c.table_name = e.table_name
          AND c.contype = 'p' AND c.columns = e.detail::jsonb)
    UNION ALL
    SELECT 'missing_foreign_key', e.table_name, e.name, e.detail
    FROM expected e JOIN tables t ON t.name = e.table_name
    WHERE e.kind = 'foreign_key' AND NOT EXISTS (
        SELECT 1 FROM constraints c WHERE c.table_name = e.table_name AND c.contype = 'f'
          AND c.columns = e.detail::jsonb->'columns' AND c.target_schema = 'public'
          AND c.target_table = e.detail::jsonb->>'target_table'
          AND c.target_columns = e.detail::jsonb->'target_columns')
    UNION ALL
    SELECT 'missing_named_check', e.table_name, e.name, e.detail
    FROM expected e JOIN tables t ON t.name = e.table_name
    WHERE e.kind = 'check' AND NOT EXISTS (
        SELECT 1 FROM constraints c WHERE c.table_name = e.table_name
          AND c.contype = 'c' AND c.name = e.name)
)
SELECT DISTINCT * FROM findings ORDER BY issue, table_name, name;
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-sql', type=Path)
    args = parser.parse_args()
    sql = diagnostic_sql()
    if args.export_sql:
        args.export_sql.parent.mkdir(parents=True, exist_ok=True)
        args.export_sql.write_text(sql, encoding='utf-8')
        print(f'Diagnostico somente de leitura: {args.export_sql}')
        return 0

    load_dotenv(ROOT / '.env')
    try:
        url = resolve_database_url(EnvSettings())
    except RuntimeError:
        print('Configure DATABASE_URL ou SUPABASE_DB_PASSWORD no .env.', file=sys.stderr)
        return 2
    if not url.startswith('postgresql'):
        print('Este diagnostico exige uma conexao PostgreSQL/Supabase.', file=sys.stderr)
        return 2
    engine = create_engine(url, connect_args={'connect_timeout': 10}, echo=False)
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text('SET TRANSACTION READ ONLY'))
                connection.execute(text("SET LOCAL statement_timeout = '30s'"))
                findings = [dict(row) for row in connection.execute(text(sql)).mappings()]
                migration_table = connection.scalar(text(
                    "SELECT to_regclass('supabase_migrations.schema_migrations')"))
                if migration_table:
                    applied = set(connection.execute(text(
                        'SELECT version FROM supabase_migrations.schema_migrations')).scalars())
                    for migration in sorted((ROOT / 'supabase/migrations').glob('*.sql')):
                        if migration.name.split('_')[0] not in applied:
                            findings.append(dict(issue='migration_not_recorded',
                                                 table_name='', name=migration.name, detail=''))
                else:
                    findings.append(dict(issue='migration_history_missing',
                                         table_name='', name='', detail=''))
                bucket = os.getenv('SUPABASE_BUCKET', 'product-images')
                if connection.scalar(text("SELECT to_regclass('storage.buckets')")):
                    bucket_public = connection.scalar(text(
                        'SELECT public FROM storage.buckets WHERE id = :bucket'), {'bucket': bucket})
                    if bucket_public is not True:
                        findings.append(dict(issue='image_bucket_missing_or_private',
                                             table_name='storage.buckets', name=bucket, detail=''))
                else:
                    findings.append(dict(issue='storage_schema_missing',
                                         table_name='storage.buckets', name=bucket, detail=''))
        print(json.dumps({'tables_checked': len(SQLModel.metadata.tables), 'findings': findings},
                         ensure_ascii=False, indent=2))
        return 1 if findings else 0
    except Exception as error:
        # Exception text may contain connection strings or other credentials.
        print(f'Falha no diagnostico ({type(error).__name__}); confira acesso e permissoes.',
              file=sys.stderr)
        return 2
    finally:
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
