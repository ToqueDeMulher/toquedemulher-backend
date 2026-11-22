"""Native PostgreSQL tests. Use only a disposable local database named tdm_test."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import make_url, text
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.v1.endpoints import payments
from app.api.v1.endpoints.abacatepay_webhook import _process
from app.core.settings import settings
from app.core.time import utc_now
from app.models.address import Address
from app.models.payment import Payment
from app.models.product import Product
from app.models.shipping import Shipment, ShippingQuote
from app.models.stock import Stock
from app.models.stockMovement import StockMovement
from app.models.user import UserInDB
from app.schemas.create_checkout import CreateCheckoutRequest
from app.services import abacatepay


@pytest.fixture
def pg(monkeypatch):
    url = os.getenv("TDM_TEST_POSTGRES_URL")
    if not url:
        pytest.skip(
            "TDM_TEST_POSTGRES_URL must point to a disposable local tdm_test database"
        )
    parsed = make_url(url)
    if parsed.host not in {"127.0.0.1", "localhost"} or parsed.database != "tdm_test":
        pytest.fail("PostgreSQL tests require a local database named tdm_test")
    admin = create_engine(url)
    schema = "test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    database = create_engine(
        url,
        connect_args={
            "options": f"-csearch_path={schema} -clock_timeout=10000 -cstatement_timeout=15000"
        },
    )
    SQLModel.metadata.create_all(database)
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "abacatepay")
    monkeypatch.setattr(settings, "ABACATEPAY_API_KEY", "dummy")
    monkeypatch.setattr(settings, "ABACATEPAY_DEV_MODE", True)
    monkeypatch.setattr(settings, "MELHOR_ENVIO_ENVIRONMENT", "sandbox")
    with Session(database) as session:
        product = Product(name="Last unit", slug="last-unit", price=49.9)
        session.add(product)
        session.flush()
        session.add(Stock(product_id=product.id, total_quantity=1))
        quote = ShippingQuote(
            environment="sandbox",
            origin_postal_code="01001000",
            postal_code="70040010",
            items=[],
            services=[],
            subtotal=Decimal("49.90"),
            expires_at=utc_now() + timedelta(minutes=15),
        )
        session.add(quote)
        session.commit()
        product_id, quote_id = product.id, quote.id
    option = {"price": 0, "company": "Fixture", "name": "Fixture"}
    monkeypatch.setattr(
        payments.shipping_service,
        "validate_selection",
        lambda selection, items, address, session: (
            session.get(ShippingQuote, quote_id),
            option,
        ),
    )

    def shipment(payment, quote, option, selection, address):
        return Shipment(
            payment_id=payment.id,
            quote_id=quote.id,
            service_id=1,
            service_name="Fixture",
            company_name="Fixture",
            cost=0,
            customer_price=0,
            delivery_min=1,
            delivery_max=1,
            recipient={},
            sender={},
        )

    monkeypatch.setattr(payments.shipping_service, "new_shipment", shipment)
    monkeypatch.setattr(
        abacatepay,
        "create_remote",
        lambda payment, **kwargs: {
            "id": "pix_char_" + str(payment.order_id),
            "status": "PENDING",
            "amount": abacatepay.cents(payment.amount),
            "devMode": True,
            "brCode": "fixture-code",
            "brCodeBase64": "data:image/png;base64,aGVsbG8=",
            "expiresAt": "2030-01-01T12:00:00Z",
        },
    )
    try:
        yield database, product_id
    finally:
        database.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def buyer(database, index):
    with Session(database) as session:
        user = UserInDB(
            name="Fixture",
            email=f"fixture{index}@example.com",
            hashed_password="unused",
        )
        session.add(user)
        session.flush()
        address = Address(
            user_id=user.id,
            cep="70040010",
            street="Fixture",
            number="1",
            neighborhood="Fixture",
            city="Brasília",
            state="DF",
        )
        session.add(address)
        session.commit()
        return user.id, address.id


def issue(database, product_id, identity, barrier, key=None):
    user_id, address_id = identity
    with Session(database) as session:
        user = session.get(UserInDB, user_id)
        payload = CreateCheckoutRequest(
            address_id=address_id,
            idempotency_key=key or uuid4(),
            items=[{"id": str(product_id), "quantity": 1}],
        )
        barrier.wait(timeout=15)
        try:
            result = payments.create_checkout(payload, session, user)
            return 200, result.order_id
        except HTTPException as exc:
            session.rollback()
            return exc.status_code, None


@pytest.mark.parametrize("buyers", [2, 10])
def test_last_unit_cannot_be_oversold_by_simultaneous_checkouts(pg, buyers):
    database, product_id = pg
    identities = [buyer(database, index) for index in range(buyers)]
    barrier = Barrier(buyers)
    with ThreadPoolExecutor(max_workers=buyers) as workers:
        results = list(
            workers.map(
                lambda identity: issue(database, product_id, identity, barrier),
                identities,
            )
        )
    assert sorted(status for status, _ in results) == [200] + [400] * (buyers - 1)
    with Session(database) as session:
        assert session.exec(select(Stock)).one().total_quantity == 0
        assert len(session.exec(select(Payment)).all()) == 1
        assert len(session.exec(select(StockMovement)).all()) == 1


def test_same_attempt_concurrent_retries_create_one_order(pg):
    database, product_id = pg
    identity = buyer(database, 0)
    key = uuid4()
    barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(
            workers.map(
                lambda _: issue(database, product_id, identity, barrier, key), range(2)
            )
        )
    assert [status for status, _ in results] == [200, 200]
    assert results[0][1] == results[1][1]
    with Session(database) as session:
        assert len(session.exec(select(Payment)).all()) == 1
        assert len(session.exec(select(StockMovement)).all()) == 1


def test_two_simultaneous_webhooks_approve_once_without_second_stock_debit(
    pg, monkeypatch
):
    database, product_id = pg
    status, _order_id = issue(database, product_id, buyer(database, 0), Barrier(1))
    assert status == 200
    with Session(database) as session:
        payment = session.exec(select(Payment)).one()
        provider_id = payment.provider_session_id
    monkeypatch.setattr(
        abacatepay,
        "lookup",
        lambda payment: {
            "id": provider_id,
            "status": "PAID",
            "amount": 4990,
            "devMode": True,
        },
    )
    barrier = Barrier(2)

    def confirm(_):
        with Session(database) as session:
            barrier.wait(timeout=15)
            return _process(session, "PIX", provider_id, "transparent.completed")

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert list(workers.map(confirm, range(2))) == [{"status": "approved"}] * 2
    with Session(database) as session:
        assert session.exec(select(Payment)).one().status == "approved"
        assert session.exec(select(Stock)).one().total_quantity == 0
        assert len(session.exec(select(StockMovement)).all()) == 1


def test_payment_migration_preserves_stripe_history_and_referential_integrity(pg):
    from pathlib import Path

    from app.models.paymentItem import PaymentItem

    database, product_id = pg
    user_id, address_id = buyer(database, 0)
    with Session(database) as session:
        payment = Payment(
            order_id=uuid4(),
            user_id=user_id,
            address_id=address_id,
            payer_email="fixture0@example.com",
            provider="stripe",
            provider_session_id="cs_legacy_fixture",
            amount=Decimal("49.90"),
            status="pending",
        )
        session.add(payment)
        session.flush()
        session.add(
            PaymentItem(
                payment_id=payment.id,
                product_id=product_id,
                title="Historical item",
                product_url="/produto/fixture",
                unit_price=Decimal("49.90"),
                quantity=1,
            )
        )
        session.commit()
    migration = (
        Path(__file__).parents[1]
        / "supabase/migrations/20261109140000_abacatepay_payments.sql"
    ).read_text()
    with database.begin() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
        assert schema.startswith("test_")
        original = connection.execute(
            text(
                "SELECT id,order_id,provider,provider_session_id,status,amount FROM payment"
            )
        ).all()
        original_items = connection.execute(
            text("SELECT id,payment_id,product_id,quantity FROM payment_item")
        ).all()
        for column in (
            "provider_method",
            "provider_dev_mode",
            "provider_creation_started",
            "provider_checked_at",
            "provider_checkout_details",
        ):
            connection.execute(
                text(f'ALTER TABLE "{schema}".payment DROP COLUMN {column}')
            )
        connection.execute(
            text(f'ALTER TABLE "{schema}".payment ENABLE ROW LEVEL SECURITY')
        )
        for _ in range(2):
            connection.exec_driver_sql(migration.replace("public.", f'"{schema}".'))
        assert (
            connection.execute(
                text(
                    "SELECT id,order_id,provider,provider_session_id,status,amount FROM payment"
                )
            ).all()
            == original
        )
        assert (
            connection.execute(
                text("SELECT id,payment_id,product_id,quantity FROM payment_item")
            ).all()
            == original_items
        )
        assert (
            connection.scalar(text("SELECT provider_creation_started FROM payment"))
            is False
        )
        assert (
            connection.scalar(
                text(
                    "SELECT relrowsecurity FROM pg_class WHERE oid='payment'::regclass"
                )
            )
            is True
        )
