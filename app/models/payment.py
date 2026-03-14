from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import Column, DateTime, Numeric
from sqlmodel import SQLModel, Field
from enum import Enum


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class PaymentStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"

class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    order_id: UUID = Field(nullable=False, index=True)
    provider: str = Field(default="mercado_pago", nullable=False, max_length=50)
    status: str = Field(default="pending", nullable=False, max_length=50, index=True)
    payer_email: str = Field(nullable=False, max_length=255)
    amount: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    currency: str = Field(default="BRL", nullable=False, max_length=10)
    provider_preference_id: Optional[str] = Field(default=None, max_length=255, index=True)
    provider_payment_id: Optional[str] = Field(default=None, max_length=255, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))