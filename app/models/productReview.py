from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy import CheckConstraint
from sqlmodel import SQLModel, Field, Relationship
from app.core.time import utc_now
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from app.core.db import UserInDB
    from app.models.product import Product

class ProductReview(SQLModel, table=True):
    __tablename__ = "product_review"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_product_review_rating_range"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: UUID = Field(foreign_key="product.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)

    rating: int
    title: Optional[str] = None
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)

    product: Optional["Product"] = Relationship(back_populates="reviews")
    user: Optional["UserInDB"] = Relationship(back_populates="reviews")