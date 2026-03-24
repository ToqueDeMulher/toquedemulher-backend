from fastapi import APIRouter, Depends, HTTPException
from app.services.loginService import LoginAndJWT
from app.core.db import _SessionDep
from typing import Annotated
from app.models.user import UserInDB
from app.schemas.addresses import AddressRequest
from app.models.address import Address
from app.schemas.message import Message

router = APIRouter()

@router.post("/addresses", response_model=Message)
def create_address(
    address_data: AddressRequest,
    session: _SessionDep,
    user: Annotated[UserInDB, Depends(LoginAndJWT.get_current_active_user)]
):
    
    try:
        new_address = Address(
            **address_data.model_dump(),
            user_id=user.id
        )

        session.add(new_address)
        session.commit()
        session.refresh(new_address)    
    except Exception as e:
        raise HTTPException(500, detail= "Error no sistema")        
    
    return  Message(mensagem="Endereço criado com sucesso")
