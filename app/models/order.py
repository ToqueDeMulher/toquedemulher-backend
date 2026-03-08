from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey,
    Text, Enum, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base


class OrderStatus(str, enum.Enum):
    pending = "pending"               # Aguardando pagamento
    payment_confirmed = "payment_confirmed"  # Pagamento confirmado
    processing = "processing"         # Em processamento
    shipped = "shipped"               # Enviado
    delivered = "delivered"           # Entregue
    cancelled = "cancelled"           # Cancelado
    refunded = "refunded"             # Reembolsado


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    order_number = Column(String(20), unique=True, index=True, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)

    # Valores
    subtotal = Column(Float, nullable=False)
    shipping_cost = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total = Column(Float, nullable=False)

    # Endereço de entrega (snapshot no momento do pedido)
    shipping_address = Column(JSON, nullable=False)

    # Frete
    shipping_method = Column(String(100), nullable=True)
    tracking_code = Column(String(100), nullable=True)
    estimated_delivery = Column(String(20), nullable=True)

    # Notas
    customer_notes = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relacionamentos
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="order", uselist=False)
    tracking_history = relationship("OrderTracking", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id"), nullable=True)

    # Snapshot do produto no momento da compra
    product_name = Column(String(200), nullable=False)
    product_sku = Column(String(100), nullable=True)
    variant_name = Column(String(100), nullable=True)
    unit_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    subtotal = Column(Float, nullable=False)

    # Relacionamentos
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    variant = relationship("ProductVariant")


class OrderTracking(Base):
    __tablename__ = "order_tracking"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(OrderStatus), nullable=False)
    description = Column(String(500), nullable=True)
    location = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relacionamentos
    order = relationship("Order", back_populates="tracking_history")
