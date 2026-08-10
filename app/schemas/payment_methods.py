from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class UserPaymentMethodType(str, Enum):
    CARD = "card"
    PIX = "pix"
    BOLETO = "boleto"


class UserPaymentMethodCreate(BaseModel):
    method_type: UserPaymentMethodType
    label: Optional[str] = None
    holder_name: Optional[str] = None
    billing_document: Optional[str] = None
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    card_exp_month: Optional[int] = Field(default=None, ge=1, le=12)
    card_exp_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    is_default: bool = False

    @field_validator("card_last4")
    @classmethod
    def validate_card_last4(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        digits = "".join(char for char in value if char.isdigit())
        if len(digits) != 4:
            raise ValueError("Informe apenas os 4 ultimos digitos do cartao")

        return digits

    @model_validator(mode="after")
    def validate_card_metadata(self):
        if self.method_type != UserPaymentMethodType.CARD:
            return self

        if not self.holder_name:
            raise ValueError("Nome impresso no cartao e obrigatorio")
        if not self.card_last4:
            raise ValueError("Final do cartao e obrigatorio")
        if self.card_exp_month is None or self.card_exp_year is None:
            raise ValueError("Validade do cartao e obrigatoria")

        return self


class UserPaymentMethodUpdate(BaseModel):
    method_type: Optional[UserPaymentMethodType] = None
    label: Optional[str] = None
    holder_name: Optional[str] = None
    billing_document: Optional[str] = None
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    card_exp_month: Optional[int] = Field(default=None, ge=1, le=12)
    card_exp_year: Optional[int] = Field(default=None, ge=2000, le=2100)
    is_default: Optional[bool] = None

    @field_validator("card_last4")
    @classmethod
    def validate_card_last4(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        digits = "".join(char for char in value if char.isdigit())
        if len(digits) != 4:
            raise ValueError("Informe apenas os 4 ultimos digitos do cartao")

        return digits


class UserPaymentMethodOut(BaseModel):
    id: UUID
    method_type: str
    label: Optional[str] = None
    holder_name: Optional[str] = None
    billing_document: Optional[str] = None
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    card_exp_month: Optional[int] = None
    card_exp_year: Optional[int] = None
    is_default: bool
    created_at: datetime
    updated_at: datetime
