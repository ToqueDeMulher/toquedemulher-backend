from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel

import app.models  # noqa: F401
from app.models.product import Product
from app.models.stock import Stock
from scripts.audit_supabase import missing_stock_findings


def test_audit_detects_missing_stock_without_changing_existing_balances():
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            existing = Product(name='With stock', slug='with-stock', price=10)
            missing = Product(name='Missing stock', slug='missing-stock', price=20)
            session.add_all([existing, missing])
            session.flush()
            stock = Stock(product_id=existing.id, total_quantity=17)
            session.add(stock)
            session.commit()
            missing_id = missing.id
            stock_id = stock.id
        with engine.connect() as connection:
            findings = missing_stock_findings(connection)
            assert len(findings) == 1
            assert findings[0]['issue'] == 'missing_product_stock'
            assert findings[0]['name'].replace('-', '') == missing_id.hex
        with Session(engine) as session:
            assert session.get(Stock, stock_id).total_quantity == 17
            session.add(Stock(product_id=missing_id, total_quantity=0))
            session.commit()
        with engine.connect() as connection:
            assert missing_stock_findings(connection) == []
    finally:
        engine.dispose()
