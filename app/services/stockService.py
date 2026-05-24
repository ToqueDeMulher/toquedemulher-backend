from uuid import UUID
from fastapi import HTTPException
from sqlmodel import select
from app.models.product import Product
from app.models.stock import Stock
from app.api.dependencies import _SessionDep
from app.models.stockMovement import StockMovementType
from app.services.stockMovementService import create_stock_movement
from app.core.time import utc_now

class StockService():

    @staticmethod
    def get_product_by_slug(slug: str, session: _SessionDep) -> Product:
        product = session.exec(select(Product).where(Product.slug == slug)).first()

        if not product:
            raise HTTPException(status_code=404,detail="Produto não encontrado")

        return product

    @staticmethod
    def get_stock_by_product_id(product_id: UUID, session: _SessionDep) -> Stock:
        stock = session.exec(select(Stock).where(Stock.product_id == product_id)).first()

        if not stock:
            raise HTTPException(status_code=404,detail="Produto fora de estoque")

        return stock

    def decrease_stock_quantity(slug: str, quantity_to_remove: int, session: _SessionDep) -> Stock:
        if quantity_to_remove <= 0:
            raise HTTPException(status_code=400,detail="A quantidade removida deve ser maior que zero")

        product = StockService.get_product_by_slug(slug=slug, session=session)
        stock = StockService.get_stock_by_product_id(product_id=product.id, session=session)

        if stock.total_quantity < quantity_to_remove:
            raise HTTPException(status_code=400,detail=f"Estoque insuficiente para o produto {product.name}")

        stock.total_quantity -= quantity_to_remove

        session.add(stock)

        return stock

    def adjust_stock_quantity(slug: str, quantity: int, session: _SessionDep):
        if quantity < 0:
            raise HTTPException(status_code=400,detail="A quantidade não pode ser negativa")

        product = StockService.get_product_by_slug(slug=slug, session=session)
        stock = StockService.get_stock_by_product_id(product_id=product.id, session=session)

        old_quantity = stock.total_quantity
        difference = quantity - old_quantity

        stock.total_quantity = quantity
        stock.updated_at = utc_now()

        create_stock_movement(
            session=session,
            product_id=product.id,
            stock_id=stock.id,
            movement_type=StockMovementType.ADJUSTMENT,
            quantity=difference,
            reason=f"Ajuste manual de estoque. Antes: {old_quantity}, depois: {quantity}"
        )

        session.add(stock)

        return product, stock, old_quantity, difference