from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.dependencies import CurrentUser, addToDB
from app.core.db import _SessionDep
from app.models.userPaymentMethod import UserPaymentMethod
from app.schemas.message import Message
from app.schemas.payment_methods import (
    UserPaymentMethodCreate,
    UserPaymentMethodOut,
    UserPaymentMethodUpdate,
)

router = APIRouter(prefix="/payment-methods")


def _unset_default_payment_methods(session: _SessionDep, user_id: UUID) -> None:
    methods = session.exec(
        select(UserPaymentMethod).where(
            UserPaymentMethod.user_id == user_id,
            UserPaymentMethod.is_default == True,  # noqa: E712
        )
    ).all()

    for method in methods:
        method.is_default = False
        method.updated_at = datetime.now(timezone.utc)
        session.add(method)


def _clear_card_fields_for_non_card(method: UserPaymentMethod) -> None:
    if method.method_type == "card":
        return

    method.card_brand = None
    method.card_last4 = None
    method.card_exp_month = None
    method.card_exp_year = None


def _validate_payment_method_state(method: UserPaymentMethod) -> None:
    if method.method_type != "card":
        return

    if not method.holder_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nome impresso no cartao e obrigatorio",
        )
    if not method.card_last4 or len(method.card_last4) != 4:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Final do cartao e obrigatorio",
        )
    if method.card_exp_month is None or method.card_exp_year is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Validade do cartao e obrigatoria",
        )


@router.get("/", response_model=list[UserPaymentMethodOut])
def list_payment_methods(user: CurrentUser, session: _SessionDep):
    return session.exec(
        select(UserPaymentMethod)
        .where(UserPaymentMethod.user_id == user.id)
        .order_by(UserPaymentMethod.is_default.desc(), UserPaymentMethod.created_at.desc())
    ).all()


@router.post(
    "/",
    response_model=UserPaymentMethodOut,
    status_code=status.HTTP_201_CREATED,
)
def create_payment_method(
    payload: UserPaymentMethodCreate,
    session: _SessionDep,
    user: CurrentUser,
):
    if payload.is_default:
        _unset_default_payment_methods(session, user.id)

    create_data = payload.model_dump()
    create_data["method_type"] = payload.method_type.value
    method = UserPaymentMethod(
        **create_data,
        user_id=user.id,
    )
    _clear_card_fields_for_non_card(method)

    addToDB(method, session)
    return method


@router.put("/{payment_method_id}", response_model=UserPaymentMethodOut)
def update_payment_method(
    payment_method_id: UUID,
    payload: UserPaymentMethodUpdate,
    session: _SessionDep,
    user: CurrentUser,
):
    method = session.exec(
        select(UserPaymentMethod).where(
            UserPaymentMethod.id == payment_method_id,
            UserPaymentMethod.user_id == user.id,
        )
    ).first()

    if not method:
        raise HTTPException(status_code=404, detail="Metodo de pagamento nao encontrado")

    update_data = payload.model_dump(exclude_unset=True)
    if "method_type" in update_data and update_data["method_type"] is not None:
        update_data["method_type"] = update_data["method_type"].value

    for key, value in update_data.items():
        setattr(method, key, value)

    _clear_card_fields_for_non_card(method)
    _validate_payment_method_state(method)

    if method.is_default:
        _unset_default_payment_methods(session, user.id)
        method.is_default = True

    method.updated_at = datetime.now(timezone.utc)
    addToDB(method, session)
    return method


@router.delete("/{payment_method_id}", response_model=Message)
def delete_payment_method(
    payment_method_id: UUID,
    session: _SessionDep,
    user: CurrentUser,
):
    method = session.exec(
        select(UserPaymentMethod).where(
            UserPaymentMethod.id == payment_method_id,
            UserPaymentMethod.user_id == user.id,
        )
    ).first()

    if not method:
        raise HTTPException(status_code=404, detail="Metodo de pagamento nao encontrado")

    session.delete(method)
    session.commit()

    return Message(mensagem="Metodo de pagamento removido com sucesso")
