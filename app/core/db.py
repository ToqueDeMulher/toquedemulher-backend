from typing import Annotated
from sqlmodel import SQLModel, create_engine, Session
from app.core.settings import settings

from app.models.coupon import Coupon
from app.models.user import UserInDB
from app.models.address import Address
from app.models.product import Product
from app.models.cart import Cart
from app.models.cartItem import CartItem
from app.models.payment import Payment
from app.models.paymentItem import PaymentItem
from app.models.order import Order
from app.models.orderItem import OrderItem
from app.models.stock_batch import StockBatch
from app.models.supplier_product import SupplierProduct

from fastapi import Depends


class Database:

    engine = create_engine(settings.DATABASE_URL, echo=True) 

    @staticmethod
    def create_db_and_tables():
        SQLModel.metadata.create_all(Database.engine)

    @staticmethod
    def get_session():
        with Session(Database.engine) as session:
            yield session
    
    @staticmethod
    def SessionLocal() -> Session:
        return Session(Database.engine)


_SessionDep = Annotated[Session, Depends(Database.get_session)]

Database.SessionDep = _SessionDep
