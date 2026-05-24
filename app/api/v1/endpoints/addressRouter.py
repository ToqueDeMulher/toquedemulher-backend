from fastapi import APIRouter, HTTPException
from app.core.db import _SessionDep
from app.schemas.addresses import AddressRequest, AddressChangeRequest
from app.models.address import Address
from app.models.user import UserInDB
from app.schemas.message import Message
from app.api.dependencies import addToDB, CurrentUser
from sqlmodel import select
from uuid import UUID

router = APIRouter(prefix="/addresses")

@router.post("/", response_model=Message, status_code=201)
def create_address(address_data: AddressRequest, session: _SessionDep, user: CurrentUser):
    
    try:
        new_address = Address(
            **address_data.model_dump(),
            user_id=user.id
        )

        addToDB(new_address, session)

    except Exception as e:
        session.rollback()
        print("Erro ao criar address:", repr(e))
        raise HTTPException(500, detail= "Error no sistema")        
    
    return  Message(mensagem="Endereço criado com sucesso")

@router.get("/")
def getAddresses(user: CurrentUser, session: _SessionDep):
    addresses = session.exec(
        select(Address).where(Address.user_id == user.id)
        ).all()
    
    return addresses

@router.delete("/{address_id}")
def deleteAdrress(address_id: UUID, user: CurrentUser, session: _SessionDep):

    address_to_delete = session.get(Address, address_id)
    
    if not address_to_delete:
        raise HTTPException(status_code=404, detail="Endereço não encontrado")

    if address_to_delete.user_id != user.id:
        raise HTTPException(status_code=403, detail="Você não tem permissão para deletar este endereço")

    session.delete(address_to_delete)
    session.commit()

    return Message(mensagem="Endereço deletado com sucesso")


@router.put("/{address_id}")
def changeAddress(
    address_id: UUID,
    data:AddressChangeRequest,
    session: _SessionDep,
    user: CurrentUser ):

    if not session.exec(select(UserInDB).where(UserInDB.id == user.id)).first():
        raise HTTPException(status_code=404, detail="Usuário não encontrado" )
    
    address = session.exec(
        select(Address).where(
            Address.id == address_id,
            Address.user_id == user.id
        )
    ).first()

    if not address:
        raise HTTPException(status_code=404, detail="Endereço não encontrado ou não pertence ao usuário" )

    update_data = data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(address, key, value)
    
    try:
        addToDB(address, session)
    except Exception as e:
        session.rollback()
        print("Erro ao atualizar address:", repr(e))
        raise HTTPException(status_code=500, detail="Erro no sistema")

    return Message(mensagem="Endereço atualizado com sucesso")
