import logging
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.dependencies import CurrentUser
from app.core.db import _SessionDep
from app.models.address import Address
from app.models.payment import Payment, PaymentStatus
from app.models.paymentItem import PaymentItem
from app.models.product import Product
from app.models.stock import Stock
from app.schemas.create_checkout import CheckoutResponse, CreateCheckoutRequest
from app.services.checkoutService import create_checkout_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(payload: CreateCheckoutRequest, session: _SessionDep, user: CurrentUser):
    """Cria uma sessão de checkout Stripe com reserva atômica de estoque."""

    total_amount = Decimal("0")
    order_id = uuid4()

    try:
        # Toda a operação — validação de estoque, criação do payment e dos itens —
        # roda dentro de uma única transação para garantir atomicidade.
        with session.begin():
            # Verifica endereço ainda dentro da transação
            address = session.exec(
                select(Address).where(
                    Address.id == payload.address_id,
                    Address.user_id == user.id,
                )
            ).first()
            if not address:
                raise HTTPException(
                    status_code=404,
                    detail="Endereço não encontrado ou não pertence ao usuário",
                )

            # Valida produtos e reserva estoque (SELECT FOR UPDATE evita overselling)
            for item in payload.items:
                product = session.exec(
                    select(Product).where(Product.slug == item.slug)
                ).first()
                if not product:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Produto '{item.slug}' não encontrado",
                    )

                stock = session.exec(
                    select(Stock)
                    .where(Stock.product_id == product.id)
                    .with_for_update()
                ).first()
                if not stock:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Produto '{product.name}' sem estoque cadastrado",
                    )
                if stock.total_quantity < item.quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Estoque insuficiente para '{product.name}'",
                    )

                total_amount += product.price * item.quantity
                stock.total_quantity -= item.quantity

            # Cria sessão no Stripe (fora do banco, mas ainda dentro do try)
            stripe_session = create_checkout_session(payload, order_id)

            payment = Payment(
                order_id=order_id,
                user_id=user.id,
                address_id=payload.address_id,
                payer_email=user.email,
                amount=total_amount,
                provider_session_id=stripe_session.id,
                status=PaymentStatus.PENDING,
            )
            session.add(payment)
            session.flush()

            for item in payload.items:
                session.add(PaymentItem(
                    payment_id=payment.id,
                    title=item.name,
                    product_url=item.product_url,
                    unit_price=Decimal(str(item.unit_price)),
                    quantity=item.quantity,
                ))

        session.refresh(payment)
        logger.info("Checkout criado: payment_id=%s order_id=%s", payment.id, order_id)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro ao criar checkout: order_id=%s", order_id)
        raise HTTPException(status_code=500, detail="Erro ao criar checkout") from exc

    return CheckoutResponse(
        client_secret=stripe_session.client_secret,
        session_id=stripe_session.id,
    )