import pytest
from sqlmodel import Session, select

from tests.test_auth import client, engine, clean_db, create_admin_token


def test_product_creation_rejects_negative_price():
    token = create_admin_token()
    response = client.post('/api/v1/products', headers={'Authorization': f'Bearer {token}'},
                           json={'name': 'Invalid price', 'price': -1})
    assert response.status_code == 422


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '1e309'])
def test_non_finite_product_price_returns_json_422_without_writes(value):
    from app.models.product import Product

    token = create_admin_token()
    response = client.post('/api/v1/products', headers={
        'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        content='{"name":"Invalid number","price":' + value + '}')
    assert response.status_code == 422
    assert response.json()['detail']
    with Session(engine) as session:
        assert session.exec(select(Product)).all() == []
