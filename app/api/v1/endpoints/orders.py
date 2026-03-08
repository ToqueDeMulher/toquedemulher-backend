from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import uuid

from app.db.base import get_db
from app.models.user import User, Address
from app.models.cart import Cart, CartItem
from app.models.order import Order, OrderItem, OrderTracking, OrderStatus
from app.models.payment import Payment, PaymentStatus, PaymentMethod, PaymentProvider
from app.schemas.order import OrderCreate, OrderOut, OrderListOut, OrderStatusUpdate
from app.api.v1.deps import get_current_active_user, get_current_admin
from app.services import payment_service
from app.services.email_service import send_order_confirmation_email, send_order_shipped_email

router = APIRouter(prefix="/orders", tags=["Pedidos"])


def _generate_order_number() -> str:
    """Gera um número de pedido único."""
    return f"TM{datetime.utcnow().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    order_in: OrderCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Cria um novo pedido a partir do carrinho do usuário."""
    # Verificar carrinho
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Carrinho vazio.",
        )

    # Verificar endereço
    address = db.query(Address).filter(
        Address.id == order_in.address_id, Address.user_id == current_user.id
    ).first()
    if not address:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endereço não encontrado.")

    # Calcular valores
    subtotal = sum(item.subtotal for item in cart.items)
    shipping_cost = 15.90  # Valor fixo por enquanto; integrar com API de frete futuramente
    total = subtotal + shipping_cost

    # Snapshot do endereço
    shipping_address = {
        "street": address.street,
        "number": address.number,
        "complement": address.complement,
        "neighborhood": address.neighborhood,
        "city": address.city,
        "state": address.state,
        "zip_code": address.zip_code,
    }

    # Criar pedido
    order = Order(
        user_id=current_user.id,
        order_number=_generate_order_number(),
        status=OrderStatus.pending,
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        discount=0.0,
        total=total,
        shipping_address=shipping_address,
        shipping_method=order_in.shipping_method,
        customer_notes=order_in.customer_notes,
    )
    db.add(order)
    db.flush()

    # Criar itens do pedido
    for cart_item in cart.items:
        product = cart_item.product
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            variant_id=cart_item.variant_id,
            product_name=product.name,
            product_sku=product.sku,
            variant_name=cart_item.variant.name if cart_item.variant else None,
            unit_price=cart_item.unit_price,
            quantity=cart_item.quantity,
            subtotal=cart_item.subtotal,
        )
        db.add(order_item)

        # Reduzir estoque
        if cart_item.variant_id and cart_item.variant:
            cart_item.variant.stock_quantity -= cart_item.quantity
        else:
            product.stock_quantity -= cart_item.quantity

    # Registro de rastreamento inicial
    tracking = OrderTracking(
        order_id=order.id,
        status=OrderStatus.pending,
        description="Pedido criado, aguardando pagamento.",
    )
    db.add(tracking)

    # Processar pagamento
    payment_result = None
    if order_in.payment_method == PaymentMethod.pix:
        payment_result = payment_service.create_pix_payment(
            order_number=order.order_number,
            amount=total,
            payer_email=current_user.email,
            payer_name=current_user.full_name,
            payer_cpf=current_user.cpf or "00000000000",
        )
    elif order_in.payment_method == PaymentMethod.boleto:
        payment_result = payment_service.create_boleto_payment(
            order_number=order.order_number,
            amount=total,
            payer_email=current_user.email,
            payer_name=current_user.full_name,
            payer_cpf=current_user.cpf or "00000000000",
            payer_address=shipping_address,
        )
    elif order_in.payment_method == PaymentMethod.credit_card and order_in.card_token:
        payment_result = payment_service.create_credit_card_payment(
            order_number=order.order_number,
            amount=total,
            payer_email=current_user.email,
            payer_name=current_user.full_name,
            payer_cpf=current_user.cpf or "00000000000",
            card_token=order_in.card_token,
            installments=order_in.installments or 1,
        )

    # Criar registro de pagamento
    payment = Payment(
        order_id=order.id,
        provider=order_in.payment_provider,
        method=order_in.payment_method,
        status=PaymentStatus.pending,
        amount=total,
    )

    if payment_result and payment_result.get("success"):
        payment.provider_payment_id = payment_result.get("provider_payment_id")
        payment.pix_qr_code = payment_result.get("pix_qr_code")
        payment.pix_qr_code_base64 = payment_result.get("pix_qr_code_base64")
        payment.pix_expiration = payment_result.get("pix_expiration")
        payment.boleto_url = payment_result.get("boleto_url")
        payment.boleto_barcode = payment_result.get("boleto_barcode")
        payment.boleto_expiration = payment_result.get("boleto_expiration")
        payment.provider_response = payment_result.get("raw_response")

        # Cartão aprovado imediatamente
        if order_in.payment_method == PaymentMethod.credit_card:
            mp_status = payment_result.get("status")
            if mp_status == "approved":
                payment.status = PaymentStatus.approved
                order.status = OrderStatus.payment_confirmed
                tracking2 = OrderTracking(
                    order_id=order.id,
                    status=OrderStatus.payment_confirmed,
                    description="Pagamento aprovado.",
                )
                db.add(tracking2)

    db.add(payment)

    # Limpar carrinho
    db.query(CartItem).filter(CartItem.cart_id == cart.id).delete()

    db.commit()
    db.refresh(order)

    # Email de confirmação em background
    background_tasks.add_task(
        send_order_confirmation_email,
        current_user.email, current_user.full_name, order.order_number, order.total
    )

    return order


@router.get("/", response_model=List[OrderListOut])
def list_my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Lista os pedidos do usuário autenticado."""
    orders = db.query(Order).filter(Order.user_id == current_user.id).order_by(
        Order.created_at.desc()
    ).all()

    result = []
    for order in orders:
        result.append(OrderListOut(
            id=order.id,
            order_number=order.order_number,
            status=order.status,
            total=order.total,
            item_count=sum(item.quantity for item in order.items),
            created_at=order.created_at,
        ))
    return result


@router.get("/{order_number}", response_model=OrderOut)
def get_order(
    order_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retorna os detalhes de um pedido."""
    order = db.query(Order).filter(
        Order.order_number == order_number,
        Order.user_id == current_user.id,
    ).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")
    return order


# ─── Administração de Pedidos ─────────────────────────────────────────────────

@router.get("/admin/all", response_model=List[OrderListOut])
def list_all_orders(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Lista todos os pedidos."""
    orders = db.query(Order).order_by(Order.created_at.desc()).offset(skip).limit(limit).all()
    return [
        OrderListOut(
            id=o.id,
            order_number=o.order_number,
            status=o.status,
            total=o.total,
            item_count=sum(i.quantity for i in o.items),
            created_at=o.created_at,
        )
        for o in orders
    ]


@router.put("/admin/{order_number}/status", response_model=OrderOut)
def update_order_status(
    order_number: str,
    status_update: OrderStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    """[Admin] Atualiza o status de um pedido."""
    order = db.query(Order).filter(Order.order_number == order_number).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido não encontrado.")

    order.status = status_update.status
    if status_update.tracking_code:
        order.tracking_code = status_update.tracking_code

    tracking = OrderTracking(
        order_id=order.id,
        status=status_update.status,
        description=status_update.description,
        location=status_update.location,
    )
    db.add(tracking)
    db.commit()
    db.refresh(order)

    # Notificar cliente por email quando enviado
    if status_update.status == OrderStatus.shipped and status_update.tracking_code:
        background_tasks.add_task(
            send_order_shipped_email,
            order.user.email, order.user.full_name,
            order.order_number, status_update.tracking_code,
        )

    return order
