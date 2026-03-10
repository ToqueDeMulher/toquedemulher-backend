from typing import List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4
from datetime import datetime, date

from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship, create_engine
from app.core.settings import settings
from app.core.time import utc_now

if TYPE_CHECKING:
    from app.features.products.models import Product, ProductReview, ProductImage


# ======================================================
# ENGINE
# ======================================================

engine = create_engine(settings.DATABASE_URL, echo=settings.SQL_ECHO)


# ======================================================
# TABELAS DE LIGACAO (N:N)
# ======================================================

class UserRoleLink(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="userindb.id", primary_key=True)
    role_id: int = Field(foreign_key="roleindb.id", primary_key=True)


class OrderCouponLink(SQLModel, table=True):
    order_id: int = Field(foreign_key="order.id", primary_key=True)
    coupon_id: int = Field(foreign_key="coupon.id", primary_key=True)


# ======================================================
# USER, ROLES, ENDERECOS
# ======================================================

class RoleInDB(SQLModel, table=True):
    __tablename__ = "roleindb"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str

    users: List["UserInDB"] = Relationship(
        back_populates="roles",
        link_model=UserRoleLink,
    )


class UserInDB(SQLModel, table=True):
    __tablename__ = "userindb"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    first_name: str
    last_name: str
    cpf: str
    email: str = Field(index=True, unique=True)
    hashed_password: str
    phone: Optional[str] = None

    gender: Optional[str] = None
    birth_date: Optional[date] = None
    accepts_marketing: bool = Field(default=False)

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: Optional[datetime] = None

    roles: List[RoleInDB] = Relationship(back_populates="users", link_model=UserRoleLink)
    addresses: List["Address"] = Relationship(back_populates="user")
    orders: List["Order"] = Relationship(back_populates="user")
    carts: List["Cart"] = Relationship(back_populates="user")
    reviews: List["ProductReview"] = Relationship(back_populates="user")


class Address(SQLModel, table=True):
    __tablename__ = "address"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(foreign_key="userindb.id", index=True)

    cep: str
    street: str
    number: Optional[str] = None
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: str
    state: str
    region: Optional[str] = None
    ddd: Optional[str] = None

    is_default_shipping: bool = Field(default=False)
    is_default_billing: bool = Field(default=False)

    user: Optional[UserInDB] = Relationship(back_populates="addresses")
    orders: List["Order"] = Relationship(back_populates="address")


# ======================================================
# CARRINHO + ITENS
# ======================================================

class Cart(SQLModel, table=True):
    __tablename__ = "cart"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="userindb.id", index=True)

    status: str = Field(default="ativo")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    user: Optional[UserInDB] = Relationship(back_populates="carts")
    items: List["CartItem"] = Relationship(back_populates="cart")
    order: Optional["Order"] = Relationship(back_populates="cart")


class CartItem(SQLModel, table=True):
    __tablename__ = "cart_item"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_cart_item_quantity_non_negative"),
        CheckConstraint("unit_price_at_time >= 0", name="ck_cart_item_unit_price_non_negative"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    cart_id: UUID = Field(foreign_key="cart.id", index=True)
    product_id: UUID = Field(foreign_key="product.id", index=True)

    quantity: int
    unit_price_at_time: float
    created_at: datetime = Field(default_factory=utc_now)

    cart: Optional[Cart] = Relationship(back_populates="items")
    product: Optional["Product"] = Relationship(back_populates="cart_items")


# ======================================================
# PEDIDO + ITENS + PAGAMENTO
# ======================================================

class PaymentMethod(SQLModel, table=True):
    __tablename__ = "payment_method"

    id: Optional[int] = Field(default=None, primary_key=True)
    type_name: str

    payments: List["Payment"] = Relationship(back_populates="method")


class Order(SQLModel, table=True):
    __tablename__ = "order"
    __table_args__ = (
        CheckConstraint("final_price >= 0", name="ck_order_final_price_non_negative"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(foreign_key="userindb.id", index=True)
    cart_id: Optional[UUID] = Field(default=None, foreign_key="cart.id", index=True)
    address_id: int = Field(foreign_key="address.id", index=True)

    order_date: datetime = Field(default_factory=utc_now)
    final_price: float
    status: str

    user: Optional[UserInDB] = Relationship(back_populates="orders")
    cart: Optional[Cart] = Relationship(back_populates="order")
    address: Optional[Address] = Relationship(back_populates="orders")
    items: List["OrderItem"] = Relationship(back_populates="order")
    payments: List["Payment"] = Relationship(back_populates="order")
    coupons: List["Coupon"] = Relationship(back_populates="orders", link_model=OrderCouponLink)


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_item"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_order_item_quantity_non_negative"),
        CheckConstraint("unit_price_at_time >= 0", name="ck_order_item_unit_price_non_negative"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    product_id: UUID = Field(foreign_key="product.id", index=True)

    quantity: int
    unit_price_at_time: float

    order: Optional[Order] = Relationship(back_populates="items")
    product: Optional["Product"] = Relationship(back_populates="order_items")


class Payment(SQLModel, table=True):
    __tablename__ = "payment"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payment_amount_non_negative"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    method_id: int = Field(foreign_key="payment_method.id", index=True)

    amount: float
    payment_date: datetime = Field(default_factory=utc_now)

    order: Optional[Order] = Relationship(back_populates="payments")
    method: Optional[PaymentMethod] = Relationship(back_populates="payments")


# ======================================================
# CUPOM
# ======================================================

class Coupon(SQLModel, table=True):
    __tablename__ = "coupon"
    __table_args__ = (
        CheckConstraint("discount_value >= 0", name="ck_coupon_discount_value_non_negative"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    description: Optional[str] = None
    discount_type: str
    discount_value: float

    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    max_uses_global: Optional[int] = None
    max_uses_per_user: Optional[int] = None
    active: bool = Field(default=True)

    orders: List[Order] = Relationship(back_populates="coupons", link_model=OrderCouponLink)


def create_db_and_tables():
    print("Criando tabelas no banco...")

    from app.features.products import models as _product_models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    print("Tabelas criadas com sucesso!")


# Dependencia para sessions em rotas

def get_session():
    from sqlmodel import Session

    with Session(engine) as session:
        yield session
