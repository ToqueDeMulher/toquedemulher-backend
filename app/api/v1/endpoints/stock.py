from fastapi import APIRouter, HTTPException
from app.schemas.stock import StockRequest, GetStock
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.stock_batch import StockBatch
from app.models.stock import Stock
from app.schemas.message import Message
from sqlmodel import select
from app.core.db import _SessionDep
from app.api.dependencies import AdminUser
from app.core.time import utc_now
from typing import List
from app.services.stockService import StockService
from app.services.stockMovementService import create_stock_movement
from app.models.stockMovement import StockMovementType

router = APIRouter(prefix="/stock")

@router.post("/", status_code=200)
def add_to_stock(user: AdminUser, stock_info: StockRequest, session: _SessionDep ):
    
    try:
        supplier = session.exec(select(Supplier).where(Supplier.name == stock_info.supplier_name)).first()
        if not supplier:
            raise HTTPException(status_code= 400, detail= "Fornecedor não existente")
        
        for item in stock_info.items: 

            product = session.exec(select(Product).where(Product.name == item.product_name)).first()
            if not product:
                raise HTTPException(status_code= 400, detail= "Produto não existente")
            
            stock = session.exec(select(Stock).where(Stock.product_id == product.id)).first()

            if not stock:
                stock = Stock(
                    product_id = product.id, 
                    total_quantity= item.quantity)
                
                session.add(stock)
                session.flush() 
            else:
                stock.total_quantity += item.quantity

            stock.updated_at = utc_now()

            batch = StockBatch(
                product_id= product.id,
                supplier_id= supplier.id,
                stock_id = stock.id,
                quantity= item.quantity,
                unit_cost=item.unit_cost,
                expiry_date= item.expiry_date)
            
            session.add(batch)

            create_stock_movement(
                session=session,
                product_id=product.id,
                stock_id=stock.id,
                movement_type=StockMovementType.IN,
                quantity=item.quantity,
                reason="Entrada de estoque por fornecedor"
            )   
        
        session.commit()

        return Message(mensagem="Estoque atualizado") 
    
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail= f"Error {e} ao atualizar o estoque")


@router.get("/")
def get_stock(session: _SessionDep, user: AdminUser)-> List[GetStock]:

    # Return all itens in stock
    stock = session.exec(select(Stock)).all()

    if not stock:
        raise HTTPException(status_code=400, detail="Estoque vazio")

    products = []

    for batch in stock:
        product = session.exec(select(Product).where(Product.id == batch.product_id)).first()

        if not product:
            continue
        products.append(GetStock(name= product.name,
                                quantity=batch.total_quantity, 
                                last_update=batch.updated_at))
    
    return products

@router.delete("/")
def delete_stock(slug: str, user: AdminUser, session: _SessionDep):

    # Deleta todo o stock e as levas relacionadas a um produto, portanto precisa de uma mensagem de confirmação de ação no front-end antes de enviar esse request.
    product = StockService.get_product_by_slug(slug, session)

    stock = StockService.get_stock_by_product_id(product.id, session)

    batches = session.exec(select(StockBatch).where(StockBatch.stock_id == stock.id)).all()

    for batch in batches:
        session.delete(batch)

    session.delete(stock)
    session.commit()

    return Message(mensagem=f"Estoque e lotes do produto {product.name} deletado com sucesso")

@router.put("/")
def change_stock(quantity: int, slug: str, user: AdminUser, session: _SessionDep):

    product, stock, old_quantity, difference = StockService.adjust_stock_quantity(
        slug=slug,
        quantity=quantity,
        session=session
    )

    session.commit()
    session.refresh(stock)

    return {
        "message": "Estoque atualizado com sucesso",
        "product": product.name,
        "slug": product.slug,
        "old_quantity": old_quantity,
        "new_quantity": stock.total_quantity,
        "difference": difference,
        "last_update": stock.updated_at
    }