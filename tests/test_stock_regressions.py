import pytest
from sqlmodel import Session, select

from tests.test_auth import client, engine, clean_db, create_admin_token


def test_stock_adjustment_refreshes_balance_loaded_before_another_update():
    from app.models.product import Product
    from app.models.stock import Stock
    from app.services.stockService import StockService

    with Session(engine) as session:
        product = Product(name='Stock fixture', slug='stock-fixture', price=10)
        session.add(product)
        session.flush()
        stock = Stock(product_id=product.id, total_quantity=10)
        session.add(stock)
        session.commit()
        stock_id = stock.id
    with Session(engine) as stale:
        cached = stale.get(Stock, stock_id)
        assert cached.total_quantity == 10
        with Session(engine) as concurrent:
            fresh = concurrent.get(Stock, stock_id)
            fresh.total_quantity = 7
            concurrent.add(fresh)
            concurrent.commit()
        _, _, previous, difference = StockService.adjust_stock_quantity('stock-fixture', 12, stale)
        assert previous == 7
        assert difference == 5
        stale.rollback()


@pytest.mark.parametrize('invalid_second_product', [False, True])
def test_stock_receipt_updates_all_items_atomically(invalid_second_product):
    from app.models.product import Product
    from app.models.stock import Stock
    from app.models.stock_batch import StockBatch
    from app.models.stockMovement import StockMovement
    from app.models.supplier import Supplier

    token = create_admin_token()
    with Session(engine) as session:
        first = Product(name='First fixture', slug='first-fixture', price=10)
        second = Product(name='Second fixture', slug='second-fixture', price=20)
        session.add_all([first, second, Supplier(name='Supplier fixture')])
        session.flush()
        session.add_all([Stock(product_id=first.id, total_quantity=4),
                         Stock(product_id=second.id, total_quantity=5)])
        session.commit()
    response = client.post('/api/v1/stock/', headers={'Authorization': f'Bearer {token}'}, json={
        'supplier_name': 'Supplier fixture', 'items': [
            {'product_name': 'First fixture', 'quantity': 3, 'unit_cost': 2},
            {'product_name': 'Missing fixture' if invalid_second_product else 'Second fixture',
             'quantity': 2, 'unit_cost': 4},
        ]})
    assert response.status_code == (400 if invalid_second_product else 200)
    with Session(engine) as session:
        quantities = sorted(stock.total_quantity for stock in session.exec(select(Stock)).all())
        assert quantities == ([4, 5] if invalid_second_product else [7, 7])
        assert len(session.exec(select(StockBatch)).all()) == (0 if invalid_second_product else 2)
        assert len(session.exec(select(StockMovement)).all()) == (0 if invalid_second_product else 2)
