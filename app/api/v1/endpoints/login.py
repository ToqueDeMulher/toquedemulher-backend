from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.dependencies import addToDB
from app.core.db import _SessionDep
from app.models.user import UserInDB
from app.schemas.user import ForgotPasswordRequest, GoogleLoginRequest, Login, Token
from app.services.google_identity_service import verify_google_credential
from app.services.loginService import LoginAndJWT

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

    access_token = LoginAndJWT.create_access_token(data={"sub": existing_user.email})
    refresh_token = LoginAndJWT.create_refresh_token(data={"sub": existing_user.email})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
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
        )
        addToDB(existing_user, session)
    elif existing_user.disabled:
        raise HTTPException(status_code=400, detail="Conta inativa")

    access_token = LoginAndJWT.create_access_token(data={"sub": existing_user.email})
    refresh_token = LoginAndJWT.create_refresh_token(data={"sub": existing_user.email})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


@router.post("/forgot-password", status_code=200)
def forgot_password(_: ForgotPasswordRequest):
    return {
        "message": "Se este email estiver cadastrado, as instrucoes de recuperacao serao enviadas.",
    }
