from sqlalchemy import Index
from sqlmodel import SQLModel, Field


class OrderCouponLink(SQLModel, table=True):
    __table_args__ = (
        Index("ix_ordercouponlink_coupon_id", "coupon_id"),
    )

    order_id: int = Field(foreign_key="order.id", primary_key=True)
    coupon_id: int = Field(foreign_key="coupon.id", primary_key=True)
