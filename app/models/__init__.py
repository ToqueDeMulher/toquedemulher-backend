# Importa todos os modelos SQLModel (Stack A) para que o SQLModel.metadata
# os conheca ao criar tabelas e para que o Alembic os encontre via este modulo.
from app.models.address import Address
from app.models.brand import Brand
from app.models.cart import Cart
from app.models.cartItem import CartItem
from app.models.category import Category
from app.models.categoryProductLink import CategoryProductLink
from app.models.coupon import Coupon
from app.models.description import Description
from app.models.order import Order
from app.models.orderCouponLink import OrderCouponLink
from app.models.orderItem import OrderItem
from app.models.payment import Payment
from app.models.paymentItem import PaymentItem
from app.models.paymentMethod import PaymentMethod
from app.models.product import Product
from app.models.productImage import ProductImage
from app.models.productReview import ProductReview
from app.models.stock import Stock
from app.models.stock_batch import StockBatch
from app.models.stockMovement import StockMovement
from app.models.supplier import Supplier
from app.models.supplier_product import SupplierProduct
from app.models.user import UserInDB

__all__ = [
    "UserInDB",
    "Address",
    "Brand",
    "Category",
    "CategoryProductLink",
    "Coupon",
    "Description",
    "Product",
    "ProductImage",
    "ProductReview",
    "Cart",
    "CartItem",
    "Order",
    "OrderItem",
    "OrderCouponLink",
    "Payment",
    "PaymentItem",
    "PaymentMethod",
    "Stock",
    "StockMovement",
    "StockBatch",
    "Supplier",
    "SupplierProduct",
]
