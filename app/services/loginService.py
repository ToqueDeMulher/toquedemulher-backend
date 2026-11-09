from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from app.core.db import Database
from app.core.settings import settings
from app.core.token_security import matches_password_fingerprint, password_fingerprint
from app.models.user import UserInDB


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/user/login")


class LoginAndJWT:
    @staticmethod
    def verify_password(password: str, password_in_db: str) -> bool:
        return pwd_context.verify(password, password_in_db)

    @staticmethod
    def hashing_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def create_user_access_token(user: UserInDB) -> str:
        return LoginAndJWT.create_access_token({
            'sub': str(user.id), 'pwd': password_fingerprint(user.hashed_password),
        })


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: Database.SessionDep,
) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
            options={'require': ['exp', 'sub', 'type', 'pwd']},
        )
        if payload.get("type") != "access":
            raise credentials_exception
        user_id = UUID(payload['sub'])
    except (InvalidTokenError, ValueError, TypeError, AttributeError):
        raise credentials_exception
    user = session.get(UserInDB, user_id)
    if user is None or not matches_password_fingerprint(payload.get('pwd'), user.hashed_password):
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[UserInDB, Depends(get_current_user)],
) -> UserInDB:
    if current_user.disabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conta inativa",
        )
    return current_user
