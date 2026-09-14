"""Shipping snapshots are private to the backend (no direct Data API access)."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, JSON, Numeric
from sqlmodel import Field, SQLModel
from app.core.time import utc_now


class ShippingConnection(SQLModel, table=True):
    __tablename__ = "shipping_connection"
    environment: str = Field(primary_key=True, max_length=16)
    access_ciphertext: Optional[str] = None
    refresh_ciphertext: Optional[str] = None
    expires_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    state_digest: Optional[str] = None
    state_expires_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )


class ShippingQuote(SQLModel, table=True):
    __tablename__ = "shipping_quote"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    environment: str = Field(max_length=16)
    origin_postal_code: str = Field(max_length=8)
    postal_code: str = Field(max_length=8)
    items: list = Field(sa_column=Column(JSON, nullable=False))
    services: list = Field(sa_column=Column(JSON, nullable=False))
    subtotal: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )


class Shipment(SQLModel, table=True):
    __tablename__ = "shipment"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    payment_id: UUID = Field(foreign_key="payment.id", unique=True, nullable=False)
    quote_id: UUID = Field(foreign_key="shipping_quote.id", nullable=False)
    service_id: int
    service_name: str
    company_name: str
    cost: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    customer_price: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    delivery_min: int
    delivery_max: int
    status: str = Field(default="pending", max_length=32)
    recipient: dict = Field(sa_column=Column(JSON, nullable=False))
    sender: dict = Field(sa_column=Column(JSON, nullable=False))
    labels: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    invoice_key: Optional[str] = Field(default=None, max_length=44)
    print_url: Optional[str] = None
    last_error: Optional[str] = None
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
