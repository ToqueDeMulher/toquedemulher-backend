from typing import Optional
from uuid import UUID, uuid4
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Numeric
from app.models.payment import Payment

class PaymentItem(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    payment_id: UUID = Field(foreign_key="payment.id", nullable=False, index=True)
    title: str = Field(nullable=False, max_length=255)
    product_url: str = Field(nullable=False, max_length=500)
    unit_price: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    quantity: int = Field(nullable=False)

    payment: Optional[Payment] = Relationship(back_populates="items")

    