from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.time import utc_now
from app.models.user import UserInDB


class UserPaymentMethod(SQLModel, table=True):
    __tablename__ = "user_payment_method"
    __table_args__ = (
        CheckConstraint(
            "method_type IN ('card', 'pix', 'boleto')",
            name="ck_user_payment_method_type",
        ),
        CheckConstraint(
            "card_exp_month IS NULL OR (card_exp_month >= 1 AND card_exp_month <= 12)",
            name="ck_user_payment_method_card_exp_month",
        ),
        CheckConstraint(
            "card_last4 IS NULL OR length(card_last4) = 4",
            name="ck_user_payment_method_card_last4",
        ),
        CheckConstraint(
            "method_type <> 'card' OR (holder_name IS NOT NULL AND card_last4 IS NOT NULL "
            "AND card_exp_month IS NOT NULL AND card_exp_year IS NOT NULL)",
            name="ck_user_payment_method_card_required_fields",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)

    method_type: str = Field(nullable=False)
    label: Optional[str] = None
    holder_name: Optional[str] = None
    billing_document: Optional[str] = None

    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None

    is_default: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    user: Optional[UserInDB] = Relationship(back_populates="payment_methods")
