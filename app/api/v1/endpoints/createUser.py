from app.models.user import UserInDB
from app.schemas.user import UserRequest, UserResponse
from sqlmodel import select
from fastapi import HTTPException, APIRouter
from app.services.loginService import LoginAndJWT
from app.core.db import _SessionDep

router = APIRouter(prefix="/user")

@router.post("/createUser", status_code=201) #201 = created
def create_user(user: UserRequest, session: _SessionDep) -> UserResponse:

    
    query = select(UserInDB).where(UserInDB.email == user.email) #criando consulta
    existing_user = session.exec(query).first()                  #executando consulta

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = UserInDB(
        name=user.name,
        cpf=user.cpf,
        email=user.email,
        hashed_password= LoginAndJWT.hashing_password(user.password),  
    )

    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    
    print("Usuário para 'salvar' no banco de dados:", db_user)

    return UserResponse(message=F"Usuario {db_user.name} criado com sucesso")