from typing import Optional
from sqlmodel import SQLModel, Field

class PaymentMethod(SQLModel, table=True):
    __tablename__ = "payment_method"

    id: Optional[int] = Field(default=None, primary_key=True)
    type_name: str