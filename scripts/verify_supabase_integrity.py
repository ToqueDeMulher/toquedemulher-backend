"""Verify Supabase integrity rules using temporary tables, without editing real rows."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.models  # noqa: E402, F401
from app.core.database_url import database_engine_options, resolve_database_url  # noqa: E402
from scripts.check_supabase_connection import EnvSettings, connection_error_hint  # noqa: E402


def expect_rejection(connection, table, values, *, constraint=None):
    try:
        with connection.begin_nested():
            connection.execute(table.insert(), values)
    except IntegrityError as error:
        if constraint:
            assert error.orig.diag.constraint_name == constraint
        else:
            assert error.orig.pgcode == '23505'
    else:
        raise AssertionError('Database accepted an invalid value')


def verification_data():
    now = datetime.now(timezone.utc)
    baselines = {
        'cart_item': dict(id=1, cart_id=uuid4(), product_id=uuid4(), quantity=1,
                          unit_price_at_time=10, created_at=now),
        'payment_item': dict(id=uuid4(), product_id=uuid4(), payment_id=uuid4(),
                             title='Diagnostic', product_url='https://example.com',
                             unit_price=10, quantity=1),
        'payment': dict(id=uuid4(), order_id=uuid4(), user_id=uuid4(), address_id=uuid4(),
                        payer_email='test@example.com', amount=10, provider='stripe',
                        status='pending', currency='BRL', created_at=now, updated_at=now),
        'stock_batch': dict(id=uuid4(), product_id=uuid4(), stock_id=uuid4(), quantity=1,
                            unit_cost=10, created_at=now, updated_at=now),
        'supplier_product': dict(id=uuid4(), supplier_id=1, product_id=uuid4(),
                                 supplier_price=10, lead_time_days=1, created_at=now),
    }
    cases = [
        ('cart_item', 'quantity', 0, 'ck_cart_item_quantity_positive'),
        ('cart_item', 'unit_price_at_time', -1, 'ck_cart_item_unit_price_non_negative'),
        ('payment_item', 'quantity', 0, 'ck_payment_item_quantity_positive'),
        ('payment_item', 'unit_price', -1, 'ck_payment_item_unit_price_non_negative'),
        ('payment', 'amount', -1, 'ck_payment_amount_non_negative'),
        ('stock_batch', 'quantity', -1, 'ck_stock_batch_quantity_non_negative'),
        ('stock_batch', 'unit_cost', -1, 'ck_stock_batch_unit_cost_non_negative'),
        ('supplier_product', 'supplier_price', -1, 'ck_supplier_product_price_non_negative'),
        ('supplier_product', 'lead_time_days', -1, 'ck_supplier_product_lead_time_non_negative'),
    ]
    return baselines, cases


def verify_rules(connection):
    baselines, cases = verification_data()
    now = datetime.now(timezone.utc)
    tables = {}
    for name in [*baselines, 'address', 'user_payment_method']:
        temp_name = 'tdm_verify_' + name
        connection.exec_driver_sql('CREATE TEMP TABLE ' + temp_name +
                                   ' (LIKE public.' + name + ' INCLUDING ALL) ON COMMIT DROP')
        # LIKE copies CHECKs and indexes, but these test tables must have no foreign keys.
        assert connection.scalar(text("SELECT count(*) FROM pg_constraint WHERE conrelid = "
                                      "to_regclass(:name) AND contype = 'f'"),
                                 {'name': 'pg_temp.' + temp_name}) == 0
        tables[name] = SQLModel.metadata.tables[name].to_metadata(MetaData(), name=temp_name)
        if name in baselines:
            connection.execute(tables[name].insert(), baselines[name])
    for name, field, value, constraint in cases:
        invalid = dict(baselines[name], **{field: value})
        # Supply serial IDs explicitly so production sequences are never used.
        invalid['id'] = 2 if name == 'cart_item' else uuid4()
        expect_rejection(connection, tables[name], invalid, constraint=constraint)
    for field in ['is_default_shipping', 'is_default_billing']:
        valid = dict(id=uuid4(), user_id=uuid4(), cep='70000000', street='Diagnostic',
                     city='Diagnostic', state='DF', is_default_shipping=False,
                     is_default_billing=False)
        valid[field] = True
        connection.execute(tables['address'].insert(), valid)
        expect_rejection(connection, tables['address'], dict(valid, id=uuid4()))
        connection.execute(tables['address'].insert(), dict(valid, id=uuid4(), user_id=uuid4()))
    method = dict(id=uuid4(), user_id=uuid4(), method_type='pix', is_default=True,
                  created_at=now, updated_at=now)
    connection.execute(tables['user_payment_method'].insert(), method)
    expect_rejection(connection, tables['user_payment_method'], dict(method, id=uuid4()))
    connection.execute(tables['user_payment_method'].insert(), dict(method, id=uuid4(), user_id=uuid4()))
    return len(cases) + 3


def integrity_sql() -> str:
    """Export the same probes for SQL Editor/Management API connections."""
    baselines, cases = verification_data()
    dialect = postgresql.dialect()

    def literal(value):
        return "'" + str(value).replace("'", "''") + "'"

    def insert(name, values):
        table = SQLModel.metadata.tables[name].to_metadata(
            MetaData(), name='tdm_verify_' + name, schema='pg_temp')
        statement = table.insert().values(**values)
        return str(statement.compile(dialect=dialect, compile_kwargs={'literal_binds': True})) + ';'

    def rejection(statement, constraint=None):
        condition = 'check_violation' if constraint else 'unique_violation'
        diagnostic = (
            'GET STACKED DIAGNOSTICS actual_constraint = CONSTRAINT_NAME;\n'
            f'IF actual_constraint IS DISTINCT FROM {literal(constraint)} THEN\n'
            "RAISE EXCEPTION 'Unexpected constraint: %', actual_constraint;\nEND IF;\n"
            if constraint else ''
        )
        return (
            'BEGIN\n' + statement + "\nRAISE EXCEPTION 'Database accepted an invalid value';\n"
            f'EXCEPTION WHEN {condition} THEN\n' + diagnostic + 'NULL;\nEND;'
        )

    statements = []
    for name in [*baselines, 'address', 'user_payment_method']:
        statements.append(f'CREATE TEMP TABLE tdm_verify_{name} '
                          f'(LIKE public.{name} INCLUDING ALL) ON COMMIT DROP;')
        if name in baselines:
            statements.append(insert(name, baselines[name]))
    for name, field, value, constraint in cases:
        invalid = dict(baselines[name], **{field: value})
        invalid['id'] = 2 if name == 'cart_item' else uuid4()
        statements.append(rejection(insert(name, invalid), constraint))
    for field in ('is_default_shipping', 'is_default_billing'):
        valid = dict(id=uuid4(), user_id=uuid4(), cep='70000000', street='Diagnostic',
                     city='Diagnostic', state='DF', is_default_shipping=False,
                     is_default_billing=False)
        valid[field] = True
        statements.extend([
            insert('address', valid),
            rejection(insert('address', dict(valid, id=uuid4()))),
            insert('address', dict(valid, id=uuid4(), user_id=uuid4())),
        ])
    now = datetime.now(timezone.utc)
    method = dict(id=uuid4(), user_id=uuid4(), method_type='pix', is_default=True,
                  created_at=now, updated_at=now)
    statements.extend([
        insert('user_payment_method', method),
        rejection(insert('user_payment_method', dict(method, id=uuid4()))),
        insert('user_payment_method', dict(method, id=uuid4(), user_id=uuid4())),
    ])
    expected = ', '.join(literal(name) for name in sorted(SQLModel.metadata.tables))
    statements.append(
        "IF (SELECT array_agg(tablename::text ORDER BY tablename) FROM pg_catalog.pg_tables "
        "WHERE schemaname = 'public') IS DISTINCT FROM ARRAY[" + expected + "]::text[] THEN\n"
        "RAISE EXCEPTION 'Public tables differ from current models';\nEND IF;"
    )
    for name in ('public.paymentitem', 'public.payment_method', 'tdm_archive.paymentitem',
                 'public.ix_cart_id', 'public.ix_payment_id', 'public.ix_payment_item_id',
                 'public.ix_product_id', 'public.ix_user_id'):
        statements.append(
            f'IF to_regclass({literal(name)}) IS NOT NULL THEN\n'
            f"RAISE EXCEPTION 'Legacy object still exists: %', {literal(name)};\nEND IF;"
        )
    statements.append("IF to_regnamespace('tdm_archive') IS NOT NULL THEN\n"
                      "RAISE EXCEPTION 'Legacy archive schema still exists';\nEND IF;")
    return (
        '-- Only temporary tables receive inserts; all IDs are supplied explicitly.\n'
        '-- ON COMMIT DROP removes the temporary tables after the atomic DO block.\n'
        'DO $tdm_verify$\nDECLARE actual_constraint text;\nBEGIN\n'
        + '\n'.join(statements) + '\nEND;\n$tdm_verify$;\n'
        + f'SELECT {len(cases) + 3} AS protections_checked, '
          f'{len(SQLModel.metadata.tables)} AS tables_checked;\n'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-sql', type=Path)
    args = parser.parse_args()
    if args.export_sql:
        args.export_sql.parent.mkdir(parents=True, exist_ok=True)
        args.export_sql.write_text(integrity_sql(), encoding='utf-8')
        print(f'Verificacao com tabelas temporarias: {args.export_sql}')
        return 0
    load_dotenv(ROOT / '.env')
    try:
        settings = EnvSettings()
        url = resolve_database_url(settings)
        if not url.startswith('postgresql'):
            print('Esta verificacao exige uma conexao PostgreSQL/Supabase.', file=sys.stderr)
            return 2
        engine = create_engine(url, **database_engine_options(
            url, pool_mode='null', connect_timeout=settings.DB_CONNECT_TIMEOUT))
    except Exception as error:
        print('Configure a conexao PostgreSQL no .env: ' + type(error).__name__, file=sys.stderr)
        return 2
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            checked = verify_rules(connection)
        print(f'Protecoes verificadas no PostgreSQL com tabelas temporarias: {checked}')
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text('SET TRANSACTION READ ONLY'))
                actual = set(connection.execute(text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).scalars())
                assert actual == set(SQLModel.metadata.tables)
                # The September 17 migration removes both legacy tables and their
                # archive schema. Query the catalogs instead of selecting a deleted table.
                for name in ('public.paymentitem', 'public.payment_method', 'tdm_archive.paymentitem'):
                    assert connection.scalar(text('SELECT to_regclass(:name)'), {'name': name}) is None
                assert connection.scalar(text("SELECT to_regnamespace('tdm_archive')")) is None
                for index in ('ix_cart_id', 'ix_payment_id', 'ix_payment_item_id',
                              'ix_product_id', 'ix_user_id'):
                    assert connection.scalar(text('SELECT to_regclass(:name)'),
                                             {'name': 'public.' + index}) is None
                print(f'{len(actual)} tabelas publicas; tabelas legadas e arquivo removidos; '
                      'cinco indices redundantes removidos.')
        return 0
    except Exception as error:
        print('Falha na verificacao: ' + type(error).__name__ + '. ' + connection_error_hint(error),
              file=sys.stderr)
        diagnostic = getattr(getattr(error, 'orig', None), 'diag', None)
        if diagnostic:
            print('SQLSTATE: ' + str(diagnostic.sqlstate), file=sys.stderr)
            print('Tabela/coluna: ' + str(diagnostic.table_name) + '/' +
                  str(diagnostic.column_name), file=sys.stderr)
        return 2
    finally:
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
