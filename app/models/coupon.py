from typing import List, Optional
from datetime import datetime
from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship
from app.models.order import Order
from app.models.orderCouponLink import OrderCouponLink


class Coupon(SQLModel, table=True):
    __tablename__ = "coupon"
    __table_args__ = (
        CheckConstraint("discount_value >= 0", name="ck_coupon_discount_value_non_negative"),
        CheckConstraint(
            "discount_type IN ('percent', 'fixed')", name="ck_coupon_discount_type"
        ),
        CheckConstraint(
            "discount_type <> 'percent' OR discount_value <= 100",
            name="ck_coupon_percent_at_most_100",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    description: Optional[str] = None
    discount_type: str  # "percent" ou "fixed" (valor em reais)
    discount_value: float

    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    max_uses_global: Optional[int] = None
    max_uses_per_user: Optional[int] = None
    active: bool = Field(default=True)

    orders: List[Order] = Relationship(back_populates="coupons", link_model=OrderCouponLink)
