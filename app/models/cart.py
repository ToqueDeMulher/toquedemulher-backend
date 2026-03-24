from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now


class Cart(SQLModel, table=True):
    __tablename__ = "cart"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)

    status: str = Field(default="ativo")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    user: Optional["UserInDB"] = Relationship(back_populates="carts")   #type: ignore
    items: List["CartItem"] = Relationship(back_populates="cart")       #type: ignore
    order: Optional["Order"] = Relationship(back_populates="cart")      #type: ignore