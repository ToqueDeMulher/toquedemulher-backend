from typing import Annotated, Dict, Any

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext
from sqlmodel import Session, select

from app.core.db import Database
from app.core.settings import settings
from app.models.user import UserInDB
from app.schemas.user import TokenData


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/user/login")


class LoginAndJWT():

    def verify_password(password, password_in_db):
        return pwd_context.verify(password, password_in_db)

    def hashing_password(password: str) -> str:
        return pwd_context.hash(password)

    def create_access_token(data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def create_refresh_token(data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    # PART 2

    def get_user(username: str, session: Session):
        query = select(UserInDB).where(UserInDB.email == username)
        user = session.exec(query).first()
        return user 

    async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], session: Database.SessionDep ):

        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload: Dict[str, Any] = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username = payload.get("sub") # retorna o email passado
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except InvalidTokenError:
            raise credentials_exception
        user = LoginAndJWT.get_user(username=token_data.username, session=session) #Pega o usuário pelo email
        if user is None:
            raise credentials_exception
        return user

    
    async def get_current_active_user(current_user: Annotated[UserInDB, Depends(get_current_user)],):
        if current_user.disabled:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user
