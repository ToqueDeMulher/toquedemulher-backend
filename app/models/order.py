from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now
from app.models.user import UserInDB
from app.models.cart import Cart
from app.models.address import Address
from app.models.orderCouponLink import OrderCouponLink



class Order(SQLModel, table=True):
    __tablename__ = "order"
    __table_args__ = (
        CheckConstraint("final_price >= 0", name="ck_order_final_price_non_negative"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    cart_id: Optional[UUID] = Field(default=None, foreign_key="cart.id", index=True)
    address_id: int = Field(foreign_key="address.id", index=True)

    order_date: datetime = Field(default_factory=utc_now)
    final_price: float
    status: str

    user: Optional[UserInDB] = Relationship(back_populates="orders")
    cart: Optional[Cart] = Relationship(back_populates="order")
    address: Optional[Address] = Relationship(back_populates="orders")
    items: List["OrderItem"] = Relationship(back_populates="order")
    coupons: List["Coupon"] = Relationship(back_populates="orders", link_model=OrderCouponLink)