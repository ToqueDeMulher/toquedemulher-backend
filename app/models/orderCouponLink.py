from sqlmodel import SQLModel, Field


class OrderCouponLink(SQLModel, table=True):
    order_id: int = Field(foreign_key="order.id", primary_key=True)
    coupon_id: int = Field(foreign_key="coupon.id", primary_key=True)