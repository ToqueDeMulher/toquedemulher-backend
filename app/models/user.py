from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, date
from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now
from app.models.productReview import ProductReview
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    CLIENT = "customer"

class UserInDB(SQLModel, table=True):
    __tablename__ = "user"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str
    cpf: Optional[str] = None
    email: str = Field(index=True, unique=True)
    hashed_password: str
    phone: Optional[str] = None

    gender: Optional[str] = None
    birth_date: Optional[date] = None
    accepts_marketing: bool = Field(default=False)

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    email_confirmed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    deleted_at: Optional[datetime] = None
    disabled: bool = Field(default=False)

    role: str = Field(default=UserRole.CLIENT.value, nullable=False)
    addresses: List["Address"] = Relationship(back_populates="user")    #type: ignore
    payment_methods: List["UserPaymentMethod"] = Relationship(back_populates="user")  # type: ignore
    orders: List["Order"] = Relationship(back_populates="user")         #type: ignore
    carts: List["Cart"] = Relationship(back_populates="user")           #type: ignore
    reviews: List["ProductReview"] = Relationship(back_populates="user")
    payments: List["Payment"] = Relationship(back_populates="user")     #type: ignore
