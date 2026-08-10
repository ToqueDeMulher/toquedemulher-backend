import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.dependencies import CurrentUser, addToDB
from app.core.db import _SessionDep
from app.models.address import Address
from app.schemas.addresses import AddressChangeRequest, AddressRequest
from app.schemas.message import Message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/addresses")


@router.post("/", response_model=Message, status_code=201)
def create_address(address_data: AddressRequest, session: _SessionDep, user: CurrentUser):
    try:
        if address_data.is_default_shipping:
            _unset_default_shipping_addresses(session, user.id)
        if address_data.is_default_billing:
            _unset_default_billing_addresses(session, user.id)

        new_address = Address(
            **address_data.model_dump(),
            user_id=user.id,
        )
        addToDB(new_address, session)
    except Exception as exc:
        session.rollback()
        logger.exception("Erro ao criar endereço: user_id=%s", user.id)
        raise HTTPException(status_code=500, detail="Erro no sistema") from exc

    return Message(mensagem="Endereço criado com sucesso")


@router.get("/")
def get_addresses(user: CurrentUser, session: _SessionDep):
    return session.exec(
        select(Address).where(Address.user_id == user.id)
    ).all()


@router.delete("/{address_id}")
def delete_address(address_id: UUID, user: CurrentUser, session: _SessionDep):
    address = session.get(Address, address_id)

    if not address:
        raise HTTPException(status_code=404, detail="Endereço não encontrado")

    if address.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para deletar este endereço",
        )

    session.delete(address)
    session.commit()

    return Message(mensagem="Endereço deletado com sucesso")


@router.put("/{address_id}")
def update_address(
    address_id: UUID,
    data: AddressChangeRequest,
    session: _SessionDep,
    user: CurrentUser,
):
    # user já foi validado pelo CurrentUser — busca direta do endereço
    address = session.exec(
        select(Address).where(
            Address.id == address_id,
            Address.user_id == user.id,
        )
    ).first()

    if not address:
        raise HTTPException(
            status_code=404,
            detail="Endereço não encontrado ou não pertence ao usuário",
        )

    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("is_default_shipping"):
        _unset_default_shipping_addresses(session, user.id)
    if update_data.get("is_default_billing"):
        _unset_default_billing_addresses(session, user.id)

    for key, value in update_data.items():
        setattr(address, key, value)

    try:
        addToDB(address, session)
    except Exception as exc:
        session.rollback()
        logger.exception("Erro ao atualizar endereço: address_id=%s", address_id)
        raise HTTPException(status_code=500, detail="Erro no sistema") from exc

    return Message(mensagem="Endereço atualizado com sucesso")


def _unset_default_shipping_addresses(session: _SessionDep, user_id: UUID) -> None:
    addresses = session.exec(
        select(Address).where(
            Address.user_id == user_id,
            Address.is_default_shipping == True,  # noqa: E712
        )
    ).all()

    for address in addresses:
        address.is_default_shipping = False
        session.add(address)


def _unset_default_billing_addresses(session: _SessionDep, user_id: UUID) -> None:
    addresses = session.exec(
        select(Address).where(
            Address.user_id == user_id,
            Address.is_default_billing == True,  # noqa: E712
        )
    ).all()

    for address in addresses:
        address.is_default_billing = False
        session.add(address)
