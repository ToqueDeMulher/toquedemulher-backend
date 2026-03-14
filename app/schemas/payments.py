from pydantic import BaseModel

class PaymentItem(BaseModel):
    id: str
    title: str
    quantity: int
    unit_price: float

