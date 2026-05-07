from uuid import UUID
from fastapi import HTTPException
from sqlmodel import select
from app.models.product import Product
from app.models.stock import Stock
from app.api.dependencies import _SessionDep


def get_product_by_slug(slug: str, session: _SessionDep) -> Product:
    product = session.exec(select(Product).where(Product.slug == slug)).first()

    if not product:
        raise HTTPException(status_code=404,detail="Produto não encontrado")

    return product


def get_stock_by_product_id(product_id: UUID, session: _SessionDep) -> Stock:
    stock = session.exec(select(Stock).where(Stock.product_id == product_id)).first()

    if not stock:
        raise HTTPException(status_code=404,detail="Produto fora de estoque")

    return stock


def change_stock_quantity(slug: str, quantity: int, session: _SessionDep) -> Stock:
    if quantity < 0:
        raise HTTPException(status_code=400,detail="A quantidade não pode ser negativa")

    product = get_product_by_slug(slug=slug, session=session)
    stock = get_stock_by_product_id(product_id=product.id, session=session)

    stock.total_quantity = quantity

    session.add(stock)

    return stock


def decrease_stock_quantity(slug: str, quantity_to_remove: int, session: _SessionDep) -> Stock:
    if quantity_to_remove <= 0:
        raise HTTPException(status_code=400,detail="A quantidade removida deve ser maior que zero")

    product = get_product_by_slug(slug=slug, session=session)
    stock = get_stock_by_product_id(product_id=product.id, session=session)

    if stock.total_quantity < quantity_to_remove:
        raise HTTPException(status_code=400,detail=f"Estoque insuficiente para o produto {product.name}")

    stock.total_quantity -= quantity_to_remove

    session.add(stock)

    return stock