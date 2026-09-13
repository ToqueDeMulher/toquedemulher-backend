import logging
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.dependencies import CurrentUser
from app.core.db import _SessionDep
from app.core.settings import settings
from app.core.time import utc_now
from app.models.address import Address
from app.models.payment import Payment, PaymentStatus
from app.models.paymentItem import PaymentItem
from app.models.product import Product
from app.models.stock import Stock
from app.schemas.create_checkout import (
    CheckoutResponse,
    CheckoutStatusResponse,
    CreateCheckoutRequest,
)
from app.services.checkoutService import (
    create_checkout_session,
    expire_checkout_session,
    retrieve_checkout_session,
)
from app.services.paymentStockService import release_checkout_stock
from app.services.stockService import StockService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"])


def _stripe_value(stripe_object, key: str):
    value = getattr(stripe_object, key, None)
    if value is None and hasattr(stripe_object, "get"):
        value = stripe_object.get(key)
    return value


def _checkout_response(stripe_session, order_id: UUID) -> CheckoutResponse:
    checkout_url = _stripe_value(stripe_session, "url")
    session_id = _stripe_value(stripe_session, "id")
    if not checkout_url or not session_id:
        raise HTTPException(
            status_code=409,
            detail="A sessão Stripe já foi finalizada ou não possui URL de pagamento",
        )

    return CheckoutResponse(
        checkout_url=checkout_url,
        session_id=session_id,
        order_id=order_id,
        client_secret=_stripe_value(stripe_session, "client_secret"),
    )


def _existing_checkout_response(payment: Payment) -> CheckoutResponse:
    if not payment.provider_session_id:
        raise HTTPException(
            status_code=409,
            detail="Checkout existente ainda não possui sessão Stripe",
        )

    try:
        stripe_session = retrieve_checkout_session(payment.provider_session_id)
    except Exception as exc:
        logger.exception(
            "Erro ao recuperar checkout Stripe: payment_id=%s",
            payment.id,
        )
        raise HTTPException(
            status_code=502,
            detail="Não foi possível recuperar a sessão de pagamento",
        ) from exc

    return _checkout_response(stripe_session, payment.order_id)


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

    existing_payment = session.exec(
        select(Payment).where(Payment.idempotency_key == payload.idempotency_key)
    ).first()
    if existing_payment:
        if existing_payment.user_id != user.id:
            raise HTTPException(status_code=409, detail="Chave de checkout já utilizada")
        return _existing_checkout_response(existing_payment)

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
                StockService.decrease_locked_stock_quantity(
                    product=product,
                    stock=stock,
                    quantity_to_remove=item.quantity,
                    session=session,
                    order_id=order_id,
                    reason="Reserva de estoque para checkout Stripe",
                )
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
                idempotency_key=str(payload.idempotency_key),
            )
            checkout_url = _stripe_value(stripe_session, "url")
            stripe_session_id = _stripe_value(stripe_session, "id")
            if not checkout_url or not stripe_session_id:
                raise HTTPException(
                    status_code=502,
                    detail="Stripe não retornou uma sessão de checkout válida",
                )

            payment = Payment(
                order_id=order_id,
                idempotency_key=payload.idempotency_key,
                user_id=user.id,
                address_id=payload.address_id,
                payer_email=user.email,
                amount=total_amount,
                provider_session_id=stripe_session_id,
                status=PaymentStatus.PENDING.value,
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
    except IntegrityError:
        session.rollback()
        existing_payment = session.exec(
            select(Payment).where(Payment.idempotency_key == payload.idempotency_key)
        ).first()
        if existing_payment and existing_payment.user_id == user.id:
            return _existing_checkout_response(existing_payment)
        raise HTTPException(status_code=409, detail="Checkout duplicado")
    except Exception as exc:
        session.rollback()
        logger.exception("Erro ao criar checkout: order_id=%s", order_id)
        raise HTTPException(status_code=500, detail="Erro ao criar checkout") from exc

    return _checkout_response(stripe_session, order_id)


@router.get("/checkout/{session_id}", response_model=CheckoutStatusResponse)
def get_checkout_status(session_id: str, session: _SessionDep, user: CurrentUser):
    payment = session.exec(
        select(Payment).where(
            Payment.provider_session_id == session_id,
            Payment.user_id == user.id,
        )
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    return CheckoutStatusResponse(
        session_id=session_id,
        order_id=payment.order_id,
        status=str(payment.status),
        amount=float(payment.amount),
        currency=payment.currency,
    )


@router.post("/checkout/{order_id}/cancel", response_model=CheckoutStatusResponse)
def cancel_checkout(order_id: UUID, session: _SessionDep, user: CurrentUser):
    payment = session.exec(
        select(Payment)
        .where(
            Payment.order_id == order_id,
            Payment.user_id == user.id,
        )
        .with_for_update()
    ).first()
    if not payment or not payment.provider_session_id:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    if str(payment.status) == PaymentStatus.PENDING.value:
        try:
            expire_checkout_session(payment.provider_session_id)
        except Exception as exc:
            logger.exception(
                "Erro ao expirar checkout Stripe: payment_id=%s",
                payment.id,
            )
            raise HTTPException(
                status_code=502,
                detail="Não foi possível cancelar a sessão de pagamento",
            ) from exc

        try:
            with session.begin_nested():
                release_checkout_stock(
                    session=session,
                    payment=payment,
                    reason="Liberação de reserva: checkout cancelado pelo cliente",
                )
                payment.status = PaymentStatus.CANCELLED.value
                payment.updated_at = utc_now()
                session.add(payment)
            session.commit()
            session.refresh(payment)
        except Exception as exc:
            session.rollback()
            logger.exception(
                "Erro ao liberar estoque do checkout: payment_id=%s",
                payment.id,
            )
            raise HTTPException(
                status_code=500,
                detail="Checkout cancelado, mas não foi possível liberar o estoque",
            ) from exc

    return CheckoutStatusResponse(
        session_id=payment.provider_session_id,
        order_id=payment.order_id,
        status=str(payment.status),
        amount=float(payment.amount),
        currency=payment.currency,
    )
