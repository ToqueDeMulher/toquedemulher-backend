from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime, date
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now
from app.models.productReview import ProductReview
from app.models.userRoleLink import UserRoleLink



class UserInDB(SQLModel, table=True):
    __tablename__ = "userindb"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    name: str
    cpf: str 
    email: str = Field(index=True, unique=True)
    hashed_password: str
    phone: Optional[str] = None

    gender: Optional[str] = None
    birth_date: Optional[date] = None
    accepts_marketing: bool = Field(default=False)

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    deleted_at: Optional[datetime] = None

    roles: List["RoleInDB"] = Relationship(back_populates="users", link_model=UserRoleLink) #type: ignore
    addresses: List["Address"] = Relationship(back_populates="user")    #type: ignore
    orders: List["Order"] = Relationship(back_populates="user")         #type: ignore
    carts: List["Cart"] = Relationship(back_populates="user")           #type: ignore
    reviews: List["ProductReview"] = Relationship(back_populates="user")