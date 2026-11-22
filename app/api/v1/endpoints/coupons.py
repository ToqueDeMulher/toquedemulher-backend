from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.dependencies import AdminUser, CurrentUser
from app.core.db import _SessionDep
from app.models.coupon import Coupon
from app.schemas.coupon import (
    AdminCouponRequest,
    AdminCouponResponse,
    AdminCouponUpdate,
    CouponValidateRequest,
    CouponValidateResponse,
)
from app.services import coupon_service
from app.services import melhor_envio as shipping_service
from app.services.brasil_api import check_rate_limit

router = APIRouter(tags=["coupons"])


@router.post("/coupons/validate", response_model=CouponValidateResponse)
def validate_coupon(
    payload: CouponValidateRequest,
    request: Request,
    session: _SessionDep,
    user: CurrentUser,
):
    """Prévia do desconto para o carrinho. O valor final é recalculado no checkout."""
    check_rate_limit(request, "coupon")
    coupon = coupon_service.find_usable(session, payload.code, user.id)
    subtotal = Decimal("0.00")
    for item in payload.items:
        product = shipping_service.resolve_product(item, session)
        if not product or not product.active or product.price <= 0:
            raise HTTPException(404, f"Produto '{item.name}' não encontrado ou inativo")
        subtotal += Decimal(str(product.price)).quantize(coupon_service.CENT) * item.quantity
    discount = coupon_service.discount_for(coupon, subtotal)
    return CouponValidateResponse(
        code=coupon.code,
        description=coupon.description,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        items_subtotal=float(subtotal),
        discount_amount=float(discount),
    )


def _naive_utc(moment: datetime | None) -> datetime | None:
    # A tabela coupon usa "timestamp without time zone"; gravamos sempre em UTC.
    if moment is None or moment.tzinfo is None:
        return moment
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def _response(session: Session, coupon: Coupon) -> AdminCouponResponse:
    return AdminCouponResponse(
        id=coupon.id,
        code=coupon.code,
        description=coupon.description,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        valid_from=coupon.valid_from,
        valid_to=coupon.valid_to,
        max_uses_global=coupon.max_uses_global,
        max_uses_per_user=coupon.max_uses_per_user,
        active=coupon.active,
        uses=coupon_service.count_uses(session, coupon.id),
    )


@router.get("/admin/coupons", response_model=list[AdminCouponResponse])
def list_coupons(session: _SessionDep, _: AdminUser):
    coupons = session.exec(select(Coupon).order_by(Coupon.id.desc())).all()
    return [_response(session, coupon) for coupon in coupons]


@router.post("/admin/coupons", response_model=AdminCouponResponse, status_code=201)
def create_coupon(payload: AdminCouponRequest, session: _SessionDep, _: AdminUser):
    code = coupon_service.normalize_code(payload.code)
    duplicate = session.exec(
        select(Coupon.id).where(func.upper(Coupon.code) == code)
    ).first()
    if duplicate:
        raise HTTPException(409, "Já existe um cupom com este código")
    coupon = Coupon(
        **payload.model_dump(exclude={"code", "valid_from", "valid_to"}),
        code=code,
        valid_from=_naive_utc(payload.valid_from),
        valid_to=_naive_utc(payload.valid_to),
    )
    session.add(coupon)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Já existe um cupom com este código") from None
    session.refresh(coupon)
    return _response(session, coupon)


@router.patch("/admin/coupons/{coupon_id}", response_model=AdminCouponResponse)
def update_coupon(
    coupon_id: int, payload: AdminCouponUpdate, session: _SessionDep, _: AdminUser
):
    """Atualiza o cupom. Pedidos já criados guardam o desconto que receberam."""
    coupon = session.get(Coupon, coupon_id)
    if not coupon:
        raise HTTPException(404, "Cupom não encontrado")
    current = AdminCouponRequest.model_construct(
        code=coupon.code,
        description=coupon.description,
        discount_type=coupon.discount_type,
        discount_value=coupon.discount_value,
        valid_from=coupon.valid_from,
        valid_to=coupon.valid_to,
        max_uses_global=coupon.max_uses_global,
        max_uses_per_user=coupon.max_uses_per_user,
        active=coupon.active,
    ).model_dump()
    try:
        merged = AdminCouponRequest(
            **{**current, **payload.model_dump(exclude_unset=True)}
        )
    except ValidationError as exc:
        raise HTTPException(
            422, exc.errors(include_url=False, include_context=False)
        ) from None
    for field in AdminCouponUpdate.model_fields:
        value = getattr(merged, field)
        if field in {"valid_from", "valid_to"}:
            value = _naive_utc(value)
        setattr(coupon, field, value)
    session.add(coupon)
    session.commit()
    session.refresh(coupon)
    return _response(session, coupon)
