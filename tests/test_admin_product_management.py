from uuid import UUID

import pytest
from sqlmodel import Session, SQLModel, select

from app.models.category import Category
from app.models.productImage import ProductImage
from app.models.stockMovement import StockMovement, StockMovementType
from tests.test_auth import client, create_admin_token, engine


@pytest.fixture(autouse=True)
def reset_database():
    SQLModel.metadata.drop_all(bind=engine)
    SQLModel.metadata.create_all(bind=engine)
    yield


def admin_headers():
    return {"Authorization": f"Bearer {create_admin_token()}"}


def add_category(name="Perfumes"):
    with Session(engine) as session:
        category = Category(name=name)
        session.add(category)
        session.commit()
        session.refresh(category)
        return category.id


def test_create_product_persists_admin_fields_as_draft():
    category_id = add_category()
    headers = admin_headers()
    response = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Perfume Floral",
            "price": 149.9,
            "active": True,
            "description": {"text": "Fragrancia floral", "usage_tips": "Aplicar na pele"},
            "category_ids": [category_id],
            "stock_quantity": 8,
        },
    )
    assert response.status_code == 200
    product_id = response.json()["id"]

    detail = client.get(f"/api/v1/products/admin/{product_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["status"] == "draft"
    assert detail.json()["description"]["text"] == "Fragrancia floral"
    assert detail.json()["category_ids"] == [category_id]
    assert detail.json()["stock_quantity"] == 8
    assert client.get("/api/v1/products").json() == []


def test_publication_requires_complete_persisted_product():
    category_id = add_category()
    headers = admin_headers()
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Produto incompleto", "price": 10, "category_ids": [category_id]},
    ).json()

    response = client.post(f"/api/v1/products/{created['id']}/publish", headers=headers)
    assert response.status_code == 422
    assert "descricao" in response.json()["detail"]
    assert "imagem" in response.json()["detail"]
    assert "estoque" in response.json()["detail"]


def test_edit_publish_unpublish_and_stock_audit_trail():
    category_id = add_category()
    headers = admin_headers()
    product_id = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": "Batom Editavel", "price": 35,
            "description": {"text": "Cor intensa"},
            "category_ids": [category_id], "stock_quantity": 2,
        },
    ).json()["id"]
    with Session(engine) as session:
        session.add(ProductImage(product_id=UUID(product_id), url="/batom.jpg", order=1))
        session.commit()

    updated = client.patch(
        f"/api/v1/products/{product_id}", headers=headers,
        json={"price": 39.9, "stock_quantity": 5},
    )
    assert updated.status_code == 200
    assert updated.json()["stock_quantity"] == 5
    with Session(engine) as session:
        movement = session.exec(select(StockMovement).order_by(StockMovement.created_at.desc())).first()
        assert movement is not None
        assert movement.movement_type == StockMovementType.ADJUSTMENT
        assert movement.quantity == 3

    assert client.post(f"/api/v1/products/{product_id}/publish", headers=headers).status_code == 200
    public = client.get("/api/v1/products").json()
    assert public[0]["name"] == "Batom Editavel" and public[0]["available"] is True
    assert client.post(f"/api/v1/products/{product_id}/unpublish", headers=headers).status_code == 200
    assert client.get("/api/v1/products").json() == []


def test_admin_search_filters_and_primary_image():
    category_id = add_category("Maquiagem")
    headers = admin_headers()
    product_id = client.post(
        "/api/v1/products", headers=headers,
        json={"name": "Gloss Rosa", "price": 20, "category_ids": [category_id]},
    ).json()["id"]
    with Session(engine) as session:
        session.add_all([
            ProductImage(product_id=UUID(product_id), url="/first.jpg", order=1),
            ProductImage(product_id=UUID(product_id), url="/second.jpg", order=2),
        ])
        session.commit()
        second_id = session.exec(select(ProductImage).where(ProductImage.order == 2)).one().id

    listed = client.get(
        f"/api/v1/products/admin/all?search=Gloss&status=draft&category_id={category_id}",
        headers=headers,
    )
    assert listed.status_code == 200 and len(listed.json()) == 1
    primary = client.post(
        f"/api/v1/products/{product_id}/images/{second_id}/primary", headers=headers,
    )
    assert primary.status_code == 200
    assert primary.json()["images"][0]["url"] == "/second.jpg"


def test_admin_product_operations_require_admin():
    assert client.get("/api/v1/products/admin/all").status_code == 401
    assert client.get("/api/v1/products/admin/categories").status_code == 401
