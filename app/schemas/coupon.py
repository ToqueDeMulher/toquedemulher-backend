from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.create_checkout import CheckoutItem


class CouponValidateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    items: list[CheckoutItem] = Field(min_length=1, max_length=100)


class CouponValidateResponse(BaseModel):
    code: str
    description: str | None = None
    discount_type: str
    discount_value: float
    items_subtotal: float
    discount_amount: float


def _utc(moment: datetime) -> datetime:
    # Datas sem fuso são tratadas como UTC, como no banco.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


class AdminCouponRequest(BaseModel):
    code: str = Field(min_length=3, max_length=50, pattern=r"^\s*[A-Za-z0-9_-]+\s*$")
    description: str | None = Field(default=None, max_length=255)
    discount_type: Literal["percent", "fixed"]
    discount_value: float = Field(gt=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    max_uses_global: int | None = Field(default=None, ge=1)
    max_uses_per_user: int | None = Field(default=None, ge=1)
    active: bool = True

    @model_validator(mode="after")
    def check_rules(self):
        if self.discount_type == "percent" and self.discount_value > 100:
            raise ValueError("Desconto percentual não pode passar de 100%")
        if (
            self.valid_from
            and self.valid_to
            and _utc(self.valid_to) <= _utc(self.valid_from)
        ):
            raise ValueError("A data final deve ser depois da data inicial")
        return self


class AdminCouponUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    discount_type: Literal["percent", "fixed"] | None = None
    discount_value: float | None = Field(default=None, gt=0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    max_uses_global: int | None = Field(default=None, ge=1)
    max_uses_per_user: int | None = Field(default=None, ge=1)
    active: bool | None = None


class AdminCouponResponse(BaseModel):
    id: int
    code: str
    description: str | None
    discount_type: str
    discount_value: float
    valid_from: datetime | None
    valid_to: datetime | None
    max_uses_global: int | None
    max_uses_per_user: int | None
    active: bool
    uses: int
