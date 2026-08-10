from typing import Annotated

from fastapi import Depends
from sqlmodel import SQLModel, Session, create_engine

from app.core.settings import settings
from app.models.address import Address
from app.models.cart import Cart
from app.models.cartItem import CartItem
from app.models.coupon import Coupon
from app.models.order import Order
from app.models.orderItem import OrderItem
from app.models.payment import Payment
from app.models.paymentItem import PaymentItem
from app.models.product import Product
from app.models.stock_batch import StockBatch
from app.models.stockMovement import StockMovement
from app.models.supplier_product import SupplierProduct
from app.models.user import UserInDB


class Database:
    engine = create_engine(settings.database_url, **settings.db_engine_options)

    @staticmethod
    def create_db_and_tables():
        SQLModel.metadata.create_all(Database.engine)

    @staticmethod
    def get_session():
        with Session(Database.engine) as session:
            yield session


_SessionDep = Annotated[Session, Depends(Database.get_session)]

Database.SessionDep = _SessionDep
