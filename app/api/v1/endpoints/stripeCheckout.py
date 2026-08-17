import logging
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, select

from app.api.dependencies import CurrentUser
from app.core.db import _SessionDep
from app.core.settings import settings
from app.models.address import Address
from app.models.payment import Payment, PaymentStatus
from app.models.paymentItem import PaymentItem
from app.models.product import Product
from app.models.stock import Stock
from app.schemas.create_checkout import CheckoutResponse, CreateCheckoutRequest
from app.services.checkoutService import create_checkout_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


def _resolve_product(item, session: Session) -> Product | None:
    if item.id:
        try:
            product_id = UUID(item.id)
        except ValueError:
            product_id = None

        if product_id:
            product = session.get(Product, product_id)
            if product:
                return product

    if item.slug:
        product = session.exec(select(Product).where(Product.slug == item.slug)).first()
        if product:
            return product

    return session.exec(select(Product).where(Product.name == item.name)).first()


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(payload: CreateCheckoutRequest, session: _SessionDep, user: CurrentUser):
    """Cria uma sessão de checkout Stripe com reserva atômica de estoque."""

    if not settings.STRIPE_SECRET_KEY.strip():
        raise HTTPException(
            status_code=500,
            detail="Stripe nao configurada. Defina STRIPE_SECRET_KEY no backend.",
        )

    total_amount = Decimal("0")
    order_id = uuid4()
    verified_items = []

    try:
        # Toda a operação — validação de estoque, criação do payment e dos itens —
        # roda dentro de um savepoint para garantir atomicidade sem conflitar com
        # a transação já aberta pelo SQLModel na injeção de dependência.
        with session.begin_nested():
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
                product = _resolve_product(item, session)
                if not product or not product.active:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Produto '{item.name}' não encontrado ou inativo",
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

                unit_price = Decimal(str(product.price))
                total_amount += unit_price * item.quantity
                stock.total_quantity -= item.quantity
                verified_items.append(
                    {
                        "product": product,
                        "name": product.name,
                        "product_url": item.product_url,
                        "unit_price": unit_price,
                        "quantity": item.quantity,
                    }
                )

            # Cria sessão no Stripe (fora do banco, mas ainda dentro do try)
            stripe_session = create_checkout_session(
                verified_items,
                order_id,
                payer_email=user.email,
            )

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

            for item in verified_items:
                session.add(
                    PaymentItem(
                        product_id=item["product"].id,
                        payment_id=payment.id,
                        title=item["name"],
                        product_url=item["product_url"],
                        unit_price=item["unit_price"],
                        quantity=item["quantity"],
                    )
                )

        session.commit()
        session.refresh(payment)
        logger.info("Checkout criado: payment_id=%s order_id=%s", payment.id, order_id)

    except HTTPException:
        session.rollback()
        raise
    except Exception as exc:
        session.rollback()
        logger.exception("Erro ao criar checkout: order_id=%s", order_id)
        raise HTTPException(status_code=500, detail="Erro ao criar checkout") from exc

    checkout_url = getattr(stripe_session, "url", None)
    if not checkout_url:
        raise HTTPException(status_code=500, detail="Stripe nao retornou URL de checkout")

    return CheckoutResponse(
        checkout_url=checkout_url,
        session_id=stripe_session.id,
        client_secret=getattr(stripe_session, "client_secret", None),
    )
