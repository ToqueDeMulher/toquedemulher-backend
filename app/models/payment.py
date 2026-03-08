from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    refunded = "refunded"
    in_process = "in_process"


class PaymentMethod(str, enum.Enum):
    credit_card = "credit_card"
    debit_card = "debit_card"
    pix = "pix"
    boleto = "boleto"


class PaymentProvider(str, enum.Enum):
    mercadopago = "mercadopago"
    pagbank = "pagbank"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Identificadores externos
    provider = Column(Enum(PaymentProvider), nullable=False)
    provider_payment_id = Column(String(200), nullable=True, index=True)  # ID no gateway
    provider_preference_id = Column(String(200), nullable=True)

    # Detalhes do pagamento
    method = Column(Enum(PaymentMethod), nullable=True)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="BRL")

    # PIX
    pix_qr_code = Column(Text, nullable=True)
    pix_qr_code_base64 = Column(Text, nullable=True)
    pix_expiration = Column(DateTime(timezone=True), nullable=True)

    # Boleto
    boleto_url = Column(String(500), nullable=True)
    boleto_barcode = Column(String(200), nullable=True)
    boleto_expiration = Column(DateTime(timezone=True), nullable=True)

    # Metadados do gateway
    provider_response = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    order = relationship("Order", back_populates="payment")
