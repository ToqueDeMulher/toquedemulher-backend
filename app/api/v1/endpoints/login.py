from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.core.db import _SessionDep
from app.models.user import UserInDB
from app.schemas.user import ForgotPasswordRequest, Login, Token
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


@router.post("/forgot-password", status_code=200)
def forgot_password(_: ForgotPasswordRequest):
    return {
        "message": "Se este email estiver cadastrado, as instrucoes de recuperacao serao enviadas.",
    }
