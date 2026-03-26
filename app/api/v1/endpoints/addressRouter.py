from fastapi import APIRouter, Depends, HTTPException
from app.services.loginService import LoginAndJWT
from app.core.db import _SessionDep
from typing import Annotated
from app.models.user import UserInDB
from app.schemas.addresses import AddressRequest
from app.models.address import Address
from app.schemas.message import Message
from app.api.dependencies import addToDB, CurrentUser
router = APIRouter()

@router.post("/addresses", response_model=Message, status_code=201)
def create_address(
    address_data: AddressRequest,
    session: _SessionDep,
    user: CurrentUser
):
    
    try:
        new_address = Address(
            **address_data.model_dump(),
            user_id=user.id
        )

        addToDB(new_address)

    except Exception as e:
        session.rollback()
        print("Erro ao criar address:", repr(e))
        raise HTTPException(500, detail= "Error no sistema")        
    
    return  Message(mensagem="Endereço criado com sucesso")
