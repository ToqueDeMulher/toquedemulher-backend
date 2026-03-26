from app.models.user import UserInDB
from app.schemas.user import UserRequest, UserResponse, ChangeUserInformationRequest
from sqlmodel import select
from fastapi import HTTPException, APIRouter
from app.services.loginService import LoginAndJWT
from app.core.db import _SessionDep
from app.api.dependencies import CurrentUser, addToDB
from app.schemas.message import Message

# PUT /user/changeProfile → nome, telefone, etc.
# PUT /user/changeEmail → fluxo separado
# PUT /user/changePassword → fluxo separado
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

@router.put("/changeUserInformation")
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


