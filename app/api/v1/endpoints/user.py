from app.models.user import UserInDB
from app.schemas.user import UserRequest, UserResponse, ChangeUserInformationRequest, ChangeEmailRequest, ChangePasswordRequest, GetUserResponse
from sqlmodel import select
from fastapi import HTTPException, APIRouter
from app.services.loginService import LoginAndJWT
from app.core.db import _SessionDep
from app.api.dependencies import CurrentUser, addToDB
from app.schemas.message import Message


router = APIRouter(prefix="/user")

@router.post("/createUser", status_code=201) #201 = created
def create_user(user: UserRequest, session: _SessionDep) -> UserResponse:

    query = select(UserInDB).where(UserInDB.email == user.email) #criando consulta
    existing_user = session.exec(query).first()                  #executando consulta

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    db_user = UserInDB(
        **user.model_dump(exclude={"password"}), #** pega um dicionário e espalha ele como argumentos nomeados.
        hashed_password= LoginAndJWT.hashing_password(user.password),  
    )

    addToDB(db_user)
    
    print("Usuário para 'salvar' no banco de dados:", db_user)

    return UserResponse(message=F"Usuario criado com sucesso")

@router.get("/me", response_model=GetUserResponse)
def getUser(session: _SessionDep, user: CurrentUser):
    db_user = session.get(UserInDB, user.id)

    if not db_user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return db_user

@router.put("/me")
def changeUserInformartions(userInformations: ChangeUserInformationRequest, session: _SessionDep, user: CurrentUser):
    
    try:
        db_user = session.exec(
            select(UserInDB).where(UserInDB.id == user.id)
        ).first()
        if not db_user:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
        
        update_data = userInformations.model_dump(exclude_unset=True) ##model_dump retorna um dicionario
        
        for key, value in update_data.items():
            setattr(db_user, key, value) #db_user.name = "name"
        
        addToDB(db_user)

        return Message(mensagem= f"Usuário{db_user.name} atualizado com sucesso")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail= f"Error ao atualizar o usuário {str(e)}")


@router.put("/me/email")
def changeEmail(data: ChangeEmailRequest, session: _SessionDep, user: CurrentUser):
    db_user = session.get(UserInDB, user.id)

    if not db_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if data.new_email == db_user.email:
        raise HTTPException(status_code=400, detail="O novo email é igual ao email atual")

    existing_user = session.exec(
        select(UserInDB).where(UserInDB.email == data.new_email)
    ).first()

    if existing_user and existing_user.id != db_user.id:
        raise HTTPException(status_code=400, detail="Email já está em uso")

    db_user.email = data.new_email

    addToDB(db_user)

    return Message(mensagem="Email atualizado com sucesso")

@router.put("/me/password")
def changePassword(data: ChangePasswordRequest, user:CurrentUser, session: _SessionDep):
    db_user = session.get(UserInDB, user.id)

    if not db_user:
        raise HTTPException(404, detail= "Usuário não encontrado")
    
    password_is_correct = LoginAndJWT.verify_password(
        data.new_password,
        db_user.hashed_password
    )

    if not password_is_correct:
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    db_user.hashed_password = LoginAndJWT.hashing_password(data.new_password)

    addToDB(db_user)

    return {"message": "Senha alterada com sucesso"}
