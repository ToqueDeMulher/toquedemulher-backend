"""Validação e cálculo de cupons de desconto do checkout."""

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.time import utc_now
from app.models.coupon import Coupon
from app.models.payment import Payment, PaymentStatus

PERCENT = "percent"
FIXED = "fixed"
DISCOUNT_TYPES = (PERCENT, FIXED)
CENT = Decimal("0.01")
MINIMUM_TOTAL = Decimal("1.00")  # menor cobrança aceita pela AbacatePay

# Pedidos que ocupam um uso do cupom. Expirados, cancelados, recusados e
# reembolsados devolvem o uso.
USAGE_STATUSES = (
    PaymentStatus.PENDING.value,
    PaymentStatus.APPROVED.value,
    PaymentStatus.DISPUTED.value,
    PaymentStatus.REFUND_PENDING.value,
)

INVALID = "Cupom inválido ou expirado."


def normalize_code(code: str) -> str:
    return code.strip().upper()


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def count_uses(session: Session, coupon_id: int, user_id: UUID | None = None) -> int:
    query = (
        select(func.count())
        .select_from(Payment)
        .where(Payment.coupon_id == coupon_id, Payment.status.in_(USAGE_STATUSES))
    )
    if user_id is not None:
        query = query.where(Payment.user_id == user_id)
    return session.exec(query).one()


def find_usable(
    session: Session, code: str, user_id: UUID, *, lock: bool = False
) -> Coupon:
    """Retorna o cupom se ele puder ser usado agora por este usuário.

    Com ``lock=True`` a linha do cupom fica travada até o fim da transação,
    para que compras simultâneas não ultrapassem os limites de uso.
    """
    normalized = normalize_code(code)
    if not normalized:
        raise HTTPException(422, INVALID)
    query = select(Coupon).where(func.upper(Coupon.code) == normalized)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    coupon = session.exec(query).first()
    now = utc_now()
    if (
        not coupon
        or not coupon.active
        or coupon.discount_type not in DISCOUNT_TYPES
        or (coupon.valid_from is not None and _aware(coupon.valid_from) > now)
        or (coupon.valid_to is not None and _aware(coupon.valid_to) < now)
    ):
        raise HTTPException(422, INVALID)
    if (
        coupon.max_uses_global is not None
        and count_uses(session, coupon.id) >= coupon.max_uses_global
    ):
        raise HTTPException(422, "Este cupom esgotou.")
    if (
        coupon.max_uses_per_user is not None
        and count_uses(session, coupon.id, user_id) >= coupon.max_uses_per_user
    ):
        raise HTTPException(
            422, "Você já usou este cupom o máximo de vezes permitido."
        )
    return coupon


def discount_for(
    coupon: Coupon, items_subtotal: Decimal, *, limit: Decimal | None = None
) -> Decimal:
    """Desconto sobre os produtos (nunca sobre o frete), em reais.

    ``limit`` é o maior desconto possível sem deixar o total abaixo do mínimo.
    """
    value = Decimal(str(coupon.discount_value))
    if coupon.discount_type == PERCENT and 0 < value <= 100:
        discount = items_subtotal * value / 100
    elif coupon.discount_type == FIXED and value > 0:
        discount = value
    else:
        raise HTTPException(422, INVALID)
    discount = min(discount.quantize(CENT, rounding=ROUND_HALF_UP), items_subtotal)
    if limit is not None:
        discount = min(discount, max(limit, Decimal("0.00")))
    return discount.quantize(CENT)
