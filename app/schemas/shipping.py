from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr, field_validator


class ShippingItem(BaseModel):
    id: Optional[str] = None
    slug: Optional[str] = None
    name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(gt=0, le=100)


class ShippingQuoteRequest(BaseModel):
    postal_code: str = Field(pattern=r"^\d{8}$")
    items: list[ShippingItem] = Field(min_length=1, max_length=100)


class ShippingSelection(BaseModel):
    quote_id: UUID
    service_id: int = Field(gt=0)
    recipient_name: str = Field(min_length=3, max_length=255)
    recipient_email: EmailStr
    recipient_phone: str = Field(pattern=r"^\d{10,11}$")
    recipient_document: str = Field(pattern=r"^\d{11}$")

    @field_validator("recipient_document")
    @classmethod
    def validate_cpf(cls, value: str):
        if len(set(value)) == 1:
            raise ValueError("CPF inválido")
        digits = [int(c) for c in value]
        for size in (9, 10):
            check = (sum(digits[i] * (size + 1 - i) for i in range(size)) * 10) % 11
            if digits[size] != (0 if check == 10 else check):
                raise ValueError("CPF inválido")
        return value


class PrepareShipmentRequest(BaseModel):
    invoice_key: str = Field(pattern=r"^\d{44}$")


class ShippingDimensions(BaseModel):
    shipping_width: float = Field(gt=0, le=300)
    shipping_height: float = Field(gt=0, le=300)
    shipping_length: float = Field(gt=0, le=300)
    shipping_weight: float = Field(gt=0, le=1000)


class ReconcileShipmentRequest(BaseModel):
    label_ids: list[UUID] = Field(min_length=1, max_length=100)
