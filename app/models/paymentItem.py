from typing import Optional
from uuid import UUID, uuid4
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Numeric, CheckConstraint
from app.models.payment import Payment
from typing import List

class PaymentItem(SQLModel, table=True):
    __tablename__ = "payment_item"
    __table_args__ = (
        CheckConstraint('quantity > 0', name='ck_payment_item_quantity_positive'),
        CheckConstraint('unit_price >= 0', name='ck_payment_item_unit_price_non_negative'),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    product_id: UUID = Field(foreign_key="product.id", index=True)
    payment_id: UUID = Field(foreign_key="payment.id", nullable=False, index=True)
    title: str = Field(nullable=False, max_length=255)
    product_url: str = Field(nullable=False, max_length=500)
    unit_price: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    quantity: int = Field(nullable=False)

    payment: Optional[Payment] = Relationship(back_populates="items")
    product: Optional["Product"] = Relationship(back_populates="payment_items") #type: ignore
    