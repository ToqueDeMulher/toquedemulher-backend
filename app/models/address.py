from typing import List, Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Index, text

from app.models.user import UserInDB

class Address(SQLModel, table=True):
    __tablename__ = "address"
    __table_args__ = (
        Index("ix_address_single_default_shipping", "user_id", unique=True,
              postgresql_where=text("is_default_shipping"), sqlite_where=text("is_default_shipping")),
        Index("ix_address_single_default_billing", "user_id", unique=True,
              postgresql_where=text("is_default_billing"), sqlite_where=text("is_default_billing")),
    )

    id: UUID = Field(default_factory= uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)

    label: Optional[str] = None  # Ex: Casa, Trabalho

    cep: str
    street: str
    number: Optional[str] = None
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: str
    state: str
    region: Optional[str] = None
    ddd: Optional[str] = None
    

    is_default_shipping: bool = Field(default=False)
    is_default_billing: bool = Field(default=False)

    user: Optional[UserInDB] = Relationship(back_populates="addresses")
    orders: List["Order"] = Relationship(back_populates="address")  # type: ignore
    payments: List["Payment"] = Relationship(back_populates="address")  # type: ignore  