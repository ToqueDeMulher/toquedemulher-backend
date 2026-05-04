from fastapi import APIRouter, HTTPException
from app.schemas.stock import StockRequest
from app.models.supplier import Supplier
from app.models.product import Product
from app.models.stock_batch import StockBatch
from app.models.stock import Stock
from app.schemas.message import Message
from sqlmodel import select
from app.core.db import _SessionDep
from app.api.dependencies import AdminUser
from app.core.time import utc_now

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
        
        session.commit()
        return Message(mensagem="Estoque atualizado") 
    
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail= f"Error {e} ao atualizar o estoque")


