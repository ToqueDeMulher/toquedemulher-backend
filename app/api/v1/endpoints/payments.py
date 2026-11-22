import logging
import time
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Response
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
from app.models.user import UserInDB
from app.schemas.create_checkout import (
    CheckoutResponse,
    CheckoutStatusResponse,
    CreateCheckoutRequest,
)
from app.services import abacatepay, coupon_service
from app.services import melhor_envio as shipping_service
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
        logger.error(
            "Falha na consulta Stripe: payment_id=%s erro=%s",
            payment.id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=502,
            detail="Não foi possível recuperar a sessão de pagamento",
        ) from exc

    return _checkout_response(stripe_session, payment.order_id)


# A emissão grava a intenção e reabre a trava antes de chamar a AbacatePay.
# Uma repetição que entre nesse intervalo deve esperar, não responder 502.
EMISSION_HANDOFF_GRACE = timedelta(milliseconds=500)


def _emission_in_flight(payment: Payment) -> bool:
    return (
        payment.status == PaymentStatus.PENDING.value
        and bool(payment.provider_creation_started)
        and not payment.provider_session_id
        and payment.provider_checkout_details is None
        and payment.provider_checked_at is not None
        and utc_now() - abacatepay.aware(payment.provider_checked_at)
        < EMISSION_HANDOFF_GRACE
    )


def _lock_after_emission_handoff(session: Session, order_id: UUID) -> Payment | None:
    deadline = time.monotonic() + EMISSION_HANDOFF_GRACE.total_seconds()
    while True:
        payment = abacatepay.payment_for_update(session, order_id)
        if (
            not payment
            or not _emission_in_flight(payment)
            or time.monotonic() >= deadline
        ):
            return payment
        # Libera a trava para a emissão em andamento retomá-la; a próxima
        # leitura espera até ela gravar o resultado.
        session.commit()
        time.sleep(0.02)


def _continue_checkout(session: Session, payment: Payment) -> CheckoutResponse:
    if payment.provider == "stripe":
        return _existing_checkout_response(payment)

    order_id = payment.order_id
    payment = _lock_after_emission_handoff(session, order_id)
    if not payment:
        raise HTTPException(404, "Pagamento não encontrado")

    if payment.status == PaymentStatus.PENDING.value:
        checked = abacatepay.refresh_from_client(session, payment)
        if (
            not payment.provider_session_id
            and payment.status == PaymentStatus.PENDING.value
        ):
            first_attempt = not payment.provider_creation_started
            if not checked and not first_attempt:
                raise HTTPException(
                    503,
                    "A emissão do checkout está em verificação. Acompanhe o pedido.",
                )
            card_product = None
            if payment.provider_method == "CARD":
                if not first_attempt:
                    session.commit()
                    raise HTTPException(
                        503,
                        "A emissão do checkout está em verificação. Acompanhe o pedido.",
                    )
                try:
                    card_product = abacatepay.prepare_card_product(payment)
                except HTTPException:
                    payment.provider_checkout_details = None
                    session.commit()
                    raise

            attempt_at = utc_now()
            payment.provider_checked_at = attempt_at
            payment.provider_checkout_details = None
            if first_attempt:
                payment.provider_creation_started = True
                # Persist intent before I/O. Hosted checkout POST cannot safely be repeated.
                session.commit()
                payment = abacatepay.payment_for_update(session, order_id)
                if not payment or (
                    not payment.provider_checked_at
                    or abacatepay.aware(payment.provider_checked_at) != attempt_at
                ):
                    raise abacatepay.unavailable()

            try:
                remote = abacatepay.create_remote(payment, card_product=card_product)
                abacatepay.apply_remote(session, payment, remote)
            except abacatepay.ChargeRejected:
                if not first_attempt:
                    session.commit()
                    raise abacatepay.unavailable() from None
                abacatepay.close_unpaid(session, payment, PaymentStatus.REJECTED.value)
            except HTTPException:
                session.commit()
                raise
        session.commit()

    checkout_url = (payment.provider_checkout_details or {}).get("checkout_url")

    return CheckoutResponse(
        session_id=str(order_id), order_id=order_id, checkout_url=checkout_url
    )


@router.get("/methods")
def payment_methods() -> list[str]:
    if settings.PAYMENT_PROVIDER == "stripe":
        return ["CARD"]
    return ["PIX", "CARD"] if settings.ABACATEPAY_CARD_ENABLED else ["PIX"]


def _resolve_product(item, session: Session) -> Product | None:
    return shipping_service.resolve_product(item, session)


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    payload: CreateCheckoutRequest, session: _SessionDep, user: CurrentUser
):
    """Reserva estoque e emite a cobrança com o total calculado no servidor."""
    legacy = settings.PAYMENT_PROVIDER == "stripe"

    # Serialize same-account attempts before reading idempotency and pending state.
    session.exec(
        select(UserInDB.id).where(UserInDB.id == user.id).with_for_update()
    ).one()
    existing_payment = session.exec(
        select(Payment).where(Payment.idempotency_key == payload.idempotency_key)
    ).first()
    if existing_payment:
        if existing_payment.user_id != user.id:
            raise HTTPException(409, "Chave de checkout já utilizada")
        return _continue_checkout(session, existing_payment)

    if legacy:
        if not settings.STRIPE_SECRET_KEY.strip():
            raise HTTPException(503, "Pagamento temporariamente indisponível.")
    else:
        if not settings.ABACATEPAY_API_KEY.strip():
            raise HTTPException(503, "Pagamento temporariamente indisponível.")
        if (
            settings.ABACATEPAY_DEV_MODE
            and shipping_service.environment() == "production"
        ):
            raise HTTPException(
                503, "Pagamento de teste exige frete em ambiente de teste."
            )
        if payload.method not in payment_methods():
            raise HTTPException(422, "Forma de pagamento indisponível.")
        pending = session.exec(
            select(Payment.id).where(
                Payment.user_id == user.id,
                Payment.provider == abacatepay.PROVIDER,
                Payment.status == PaymentStatus.PENDING.value,
            )
        ).first()
        if pending:
            raise HTTPException(
                409,
                "Já existe um pagamento pendente. Acompanhe o pedido antes de tentar novamente.",
            )

    total_amount = Decimal(0)
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

            coupon = None
            if payload.coupon_code:
                if legacy:
                    raise HTTPException(
                        422, "Cupons indisponíveis nesta forma de pagamento."
                    )
                # Trava o cupom até o commit: compras simultâneas não
                # ultrapassam o limite de usos.
                coupon = coupon_service.find_usable(
                    session, payload.coupon_code, user.id, lock=True
                )

            quote, shipping_option = shipping_service.validate_selection(
                payload.shipping, payload.items, address, session
            )
            total_amount += Decimal(str(shipping_option["price"]))

            # Valida produtos e reserva estoque (SELECT FOR UPDATE evita overselling)
            resolved = []
            for item in payload.items:
                product = _resolve_product(item, session)
                if not product or not product.active:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Produto '{item.name}' não encontrado ou inativo",
                    )
                if product.price <= 0:
                    raise HTTPException(409, "Produto indisponível para compra")

                resolved.append((product, item))

            for product, item in sorted(resolved, key=lambda pair: str(pair[0].id)):
                stock = session.exec(
                    select(Stock)
                    .where(Stock.product_id == product.id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
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

                unit_price = Decimal(str(product.price)).quantize(Decimal("0.01"))
                total_amount += unit_price * item.quantity
                StockService.decrease_locked_stock_quantity(
                    product=product,
                    stock=stock,
                    quantity_to_remove=item.quantity,
                    session=session,
                    order_id=order_id,
                    reason="Reserva de estoque para checkout",
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

            discount_amount = Decimal("0.00")
            if coupon:
                items_subtotal = sum(
                    (item["unit_price"] * item["quantity"] for item in verified_items),
                    Decimal("0.00"),
                )
                discount_amount = coupon_service.discount_for(
                    coupon,
                    items_subtotal,
                    limit=total_amount - coupon_service.MINIMUM_TOTAL,
                )
                total_amount -= discount_amount

            stripe_session = None
            stripe_session_id = None
            total_amount = total_amount.quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if not legacy and abacatepay.cents(total_amount) < 100:
                raise HTTPException(422, "O total mínimo para pagamento é R$ 1,00.")
            if legacy:
                stripe_session = create_checkout_session(
                    verified_items,
                    order_id,
                    payer_email=user.email,
                    idempotency_key=str(payload.idempotency_key),
                    shipping_amount=Decimal(str(shipping_option["price"])),
                    shipping_name=f"{shipping_option['company']} - {shipping_option['name']}",
                )
                stripe_session_id = _checkout_response(
                    stripe_session, order_id
                ).session_id

            payment = Payment(
                order_id=order_id,
                idempotency_key=payload.idempotency_key,
                user_id=user.id,
                address_id=payload.address_id,
                payer_email=user.email,
                amount=total_amount,
                coupon_id=coupon.id if coupon else None,
                discount_amount=discount_amount,
                provider_session_id=stripe_session_id,
                provider=settings.PAYMENT_PROVIDER,
                provider_method=None if legacy else payload.method,
                provider_dev_mode=None if legacy else settings.ABACATEPAY_DEV_MODE,
                status=PaymentStatus.PENDING.value,
            )
            session.add(payment)
            session.flush()
            session.add(
                shipping_service.new_shipment(
                    payment, quote, shipping_option, payload.shipping, address
                )
            )

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
            return _continue_checkout(session, existing_payment)
        raise HTTPException(status_code=409, detail="Checkout duplicado")
    except Exception as exc:
        session.rollback()
        logger.error(
            "Falha no checkout: order_id=%s erro=%s", order_id, type(exc).__name__
        )
        raise HTTPException(status_code=500, detail="Erro ao criar checkout") from exc

    if legacy:
        return _checkout_response(stripe_session, order_id)
    return _continue_checkout(session, payment)


@router.get("/checkout/active")
def active_checkout(session: _SessionDep, user: CurrentUser) -> CheckoutResponse:
    payment = session.exec(
        select(Payment).where(
            Payment.provider == abacatepay.PROVIDER,
            Payment.user_id == user.id,
            Payment.status == PaymentStatus.PENDING.value,
        )
    ).first()
    if not payment:
        raise HTTPException(404, "Nenhum pagamento pendente.")
    return CheckoutResponse(session_id=str(payment.order_id), order_id=payment.order_id)


@router.post("/checkout/{order_id}/resume", response_model=CheckoutResponse)
def resume_checkout(order_id: UUID, session: _SessionDep, user: CurrentUser):
    payment = abacatepay.payment_for_update(session, order_id, user_id=user.id)
    if not payment:
        raise HTTPException(404, "Pagamento não encontrado")
    return _continue_checkout(session, payment)


@router.get("/checkout/{session_id}", response_model=CheckoutStatusResponse)
def get_checkout_status(
    session_id: str, response: Response, session: _SessionDep, user: CurrentUser
) -> CheckoutStatusResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        order_id = UUID(session_id)
    except ValueError:
        order_id = None

    if order_id:
        payment = session.exec(
            select(Payment)
            .where(
                Payment.provider == abacatepay.PROVIDER,
                Payment.order_id == order_id,
                Payment.user_id == user.id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
    else:
        payment = session.exec(
            select(Payment).where(
                Payment.provider == "stripe",
                Payment.provider_session_id == session_id,
                Payment.user_id == user.id,
            )
        ).first()
    if not payment:
        raise HTTPException(404, "Pagamento não encontrado")

    details = {}
    if order_id and payment.status in abacatepay.ACTIVE_STATUSES:
        abacatepay.refresh_from_client(session, payment)
        session.commit()
        details = payment.provider_checkout_details or {}

    return CheckoutStatusResponse(
        session_id=session_id,
        order_id=payment.order_id,
        status=payment.status,
        amount=float(payment.amount),
        discount_amount=float(payment.discount_amount or 0),
        currency=payment.currency,
        **details,
    )


@router.post("/checkout/{order_id}/cancel", response_model=CheckoutStatusResponse)
def cancel_checkout(order_id: UUID, session: _SessionDep, user: CurrentUser):
    payment = session.exec(
        select(Payment)
        .where(
            Payment.provider == "stripe",
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
            logger.error(
                "Falha ao expirar checkout Stripe: payment_id=%s erro=%s",
                payment.id,
                type(exc).__name__,
            )
            # A previous successful expiration may have lost its response.
            # Release only after the provider confirms expiration, never on a timeout.
            try:
                remote = retrieve_checkout_session(payment.provider_session_id)
            except Exception:  # noqa: BLE001 - keep the reservation if the provider cannot confirm
                remote = None
            if not remote or _stripe_value(remote, "status") != "expired":
                raise HTTPException(
                    status_code=502,
                    detail="Não foi possível confirmar o cancelamento. Consulte seu pedido antes de tentar pagar novamente.",
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
            logger.error(
                "Falha ao liberar estoque: payment_id=%s erro=%s",
                payment.id,
                type(exc).__name__,
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
        discount_amount=float(payment.discount_amount or 0),
        currency=payment.currency,
    )
