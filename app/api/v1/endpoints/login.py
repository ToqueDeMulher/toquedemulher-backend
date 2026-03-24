from fastapi import APIRouter, HTTPException
from app.models.user import UserInDB
from app.schemas.user import Login, Token  
from sqlmodel import select
from app.services.loginService import LoginAndJWT
from app.core.db import _SessionDep

router = APIRouter(prefix="/user")

@router.post("/login", status_code=200)
def isLoged(loginCredentiasl: Login, session: _SessionDep)-> Token:

    queryEmail = select(UserInDB).where(UserInDB.email == loginCredentiasl.email)
    existingUser = session.exec(queryEmail).first()
    
    if not existingUser or not LoginAndJWT.verify_password(loginCredentiasl.password, existingUser.hashed_password):
        raise HTTPException(status_code=401, detail="incorrect Email or password")
    
    access_token = LoginAndJWT.create_access_token(data={"sub": existingUser.email}) 

    return Token(access_token=access_token, token_type="bearer") 