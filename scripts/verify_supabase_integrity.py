"""Verify Supabase integrity rules using temporary tables, without editing real rows."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.models  # noqa: E402, F401
from app.core.database_url import resolve_database_url  # noqa: E402
from scripts.check_supabase_connection import EnvSettings  # noqa: E402


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


def verify_rules(connection):
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


def main():
    load_dotenv(ROOT / '.env')
    try:
        engine = create_engine(resolve_database_url(EnvSettings()),
                               connect_args={'connect_timeout': 10}, echo=False)
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
                assert connection.scalar(text("SELECT to_regclass('public.paymentitem')")) is None
                assert connection.scalar(text('SELECT count(*) FROM tdm_archive.paymentitem')) == 0
                for role in ('anon', 'authenticated'):
                    assert not connection.scalar(text(
                        "SELECT has_schema_privilege(:role, 'tdm_archive', 'USAGE')"), {'role': role})
                for index in ('ix_cart_id', 'ix_payment_id', 'ix_payment_item_id',
                              'ix_product_id', 'ix_user_id'):
                    assert connection.scalar(text('SELECT to_regclass(:name)'),
                                             {'name': 'public.' + index}) is None
                print('24 tabelas publicas; arquivo privado preservado; cinco indices redundantes removidos.')
        return 0
    except Exception as error:
        print('Falha na verificacao: ' + type(error).__name__, file=sys.stderr)
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
