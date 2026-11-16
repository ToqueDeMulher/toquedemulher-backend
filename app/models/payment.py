from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, Numeric
from sqlmodel import Field, Relationship, SQLModel

from app.core.time import utc_now

if TYPE_CHECKING:
    from app.models.address import Address
    from app.models.paymentItem import PaymentItem
    from app.models.user import UserInDB

class PaymentStatus(str, Enum):
    PENDING   = "pending"
    APPROVED  = "approved"
    REJECTED  = "rejected"
    CANCELLED = "cancelled"
    REFUNDED  = "refunded"
    EXPIRED = "expired"
    DISPUTED = "disputed"
    REFUND_PENDING = "refund_pending"

class Payment(SQLModel, table=True):
    __tablename__ = "payment"
    __table_args__ = (
        CheckConstraint('amount >= 0', name='ck_payment_amount_non_negative'),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    order_id: UUID = Field(nullable=False, index=True)
    idempotency_key: UUID | None = Field(
        default=None,
        nullable=True,
        index=True,
        unique=True,
    )

    user_id: UUID = Field(foreign_key="user.id", nullable=False, index=True)
    address_id: UUID = Field(foreign_key="address.id", nullable=False, index=True)

    provider: str = Field(default="stripe", nullable=False)
    provider_method: str | None = Field(default=None, max_length=10)
    provider_dev_mode: bool | None = Field(default=None)
    provider_creation_started: bool = Field(default=False, nullable=False)
    provider_checked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    provider_checkout_details: dict | None = Field(
        default=None, sa_column=Column(JSON, nullable=True)
    )
    status: str = Field(default=PaymentStatus.PENDING.value, nullable=False, index=True)
    payer_email: str = Field(nullable=False, max_length=255)
    amount: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    currency: str = Field(default="BRL", nullable=False, max_length=10)
    provider_session_id: str | None = Field(default=None, max_length=255, index=True)
    provider_payment_id: str | None = Field(default=None, max_length=255, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))

    items: list["PaymentItem"] = Relationship(back_populates="payment") #type: ignore
    user: Optional["UserInDB"] = Relationship(back_populates="payments") #type: ignore
    address: Optional["Address"] = Relationship(back_populates="payments") #type: ignore
