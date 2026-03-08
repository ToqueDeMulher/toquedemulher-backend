from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime
from app.models.order import OrderStatus
from app.models.payment import PaymentMethod, PaymentProvider, PaymentStatus


class OrderItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    product_sku: Optional[str] = None
    variant_name: Optional[str] = None
    unit_price: float
    quantity: int
    subtotal: float

    class Config:
        from_attributes = True


class OrderTrackingOut(BaseModel):
    id: int
    status: OrderStatus
    description: Optional[str] = None
    location: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentOut(BaseModel):
    id: int
    provider: PaymentProvider
    method: Optional[PaymentMethod] = None
    status: PaymentStatus
    amount: float
    pix_qr_code: Optional[str] = None
    pix_qr_code_base64: Optional[str] = None
    pix_expiration: Optional[datetime] = None
    boleto_url: Optional[str] = None
    boleto_barcode: Optional[str] = None
    boleto_expiration: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    address_id: int
    shipping_method: Optional[str] = "PAC"
    customer_notes: Optional[str] = None
    payment_method: PaymentMethod
    payment_provider: PaymentProvider = PaymentProvider.mercadopago
    # Para cartão de crédito
    card_token: Optional[str] = None
    installments: Optional[int] = 1


class OrderOut(BaseModel):
    id: int
    order_number: str
    status: OrderStatus
    subtotal: float
    shipping_cost: float
    discount: float
    total: float
    shipping_address: Dict[str, Any]
    shipping_method: Optional[str] = None
    tracking_code: Optional[str] = None
    estimated_delivery: Optional[str] = None
    customer_notes: Optional[str] = None
    items: List[OrderItemOut] = []
    payment: Optional[PaymentOut] = None
    tracking_history: List[OrderTrackingOut] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderListOut(BaseModel):
    id: int
    order_number: str
    status: OrderStatus
    total: float
    item_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    description: Optional[str] = None
    tracking_code: Optional[str] = None
    location: Optional[str] = None
