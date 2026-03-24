from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel


class AddressRequest(SQLModel):
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

    is_default_shipping: bool = False
    is_default_billing: bool = False

