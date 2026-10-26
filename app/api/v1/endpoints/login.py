from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlmodel import select

from app.api.dependencies import addToDB
from app.core.db import _SessionDep
from app.core.settings import settings
from app.core.time import utc_now
from app.models.user import UserInDB
from app.schemas.message import Message
from app.schemas.user import (
    ForgotPasswordRequest,
    GoogleLoginRequest,
    Login,
    ResetPasswordRequest,
    Token,
)
from app.services.google_identity_service import verify_google_credential
from app.services.loginService import LoginAndJWT
from app.services.password_reset_service import (
    send_password_reset_flow,
    verify_password_reset_token,
)

router = APIRouter(prefix="/user")


@router.post("/login", response_model=Token, status_code=200)
def login(login_credentials: Login, session: _SessionDep) -> Token:
    existing_user = session.exec(
        select(UserInDB).where(UserInDB.email == login_credentials.email)
    ).first()

    if not existing_user or not LoginAndJWT.verify_password(
        login_credentials.password,
        existing_user.hashed_password,
    ):
        raise HTTPException(status_code=401, detail="incorrect Email or password")

    if existing_user.disabled:
        raise HTTPException(status_code=400, detail="Conta inativa")

    if settings.EMAIL_CONFIRMATION_REQUIRED and not existing_user.email_confirmed_at:
        raise HTTPException(status_code=403, detail="Confirme seu email antes de entrar")

    access_token = LoginAndJWT.create_access_token(data={"sub": existing_user.email})

    return Token(
        access_token=access_token,
        token_type="bearer",
    )


@router.post("/google", response_model=Token, status_code=200)
def login_with_google(payload: GoogleLoginRequest, session: _SessionDep) -> Token:
    google_user = verify_google_credential(payload.credential)
    existing_user = session.exec(
        select(UserInDB).where(UserInDB.email == google_user.email)
    ).first()

    if not existing_user:
        existing_user = UserInDB(
            name=google_user.name,
            email=google_user.email,
            hashed_password=LoginAndJWT.hashing_password(f"google:{google_user.sub}:{uuid4()}"),
            email_confirmed_at=utc_now(),
        )
        addToDB(existing_user, session)
    elif existing_user.disabled:
        raise HTTPException(status_code=400, detail="Conta inativa")

    access_token = LoginAndJWT.create_access_token(data={"sub": existing_user.email})

    return Token(
        access_token=access_token,
        token_type="bearer",
    )


GENERIC_FORGOT_PASSWORD_MESSAGE = (
    "Se este email estiver cadastrado, as instrucoes de recuperacao serao enviadas."
)


@router.post("/forgot-password", status_code=200)
def forgot_password(
    payload: ForgotPasswordRequest,
    session: _SessionDep,
    background_tasks: BackgroundTasks,
):
    existing_user = session.exec(
        select(UserInDB).where(UserInDB.email == payload.email)
    ).first()

    if existing_user and not existing_user.disabled:
        background_tasks.add_task(
            send_password_reset_flow, existing_user.name, existing_user.email
        )

    return {"message": GENERIC_FORGOT_PASSWORD_MESSAGE}


@router.post("/reset-password", response_model=Message, status_code=200)
def reset_password(data: ResetPasswordRequest, session: _SessionDep):
    email = verify_password_reset_token(data.token)

    if not email:
        raise HTTPException(status_code=400, detail="Token de redefinicao invalido ou expirado")

    db_user = session.exec(select(UserInDB).where(UserInDB.email == email)).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado")

    db_user.hashed_password = LoginAndJWT.hashing_password(data.new_password)
    addToDB(db_user, session)

    return Message(mensagem="Senha redefinida com sucesso")
