from typing import Annotated
from fastapi import Depends, HTTPException, status
from app.models.user import UserInDB
from app.services.loginService import LoginAndJWT
from app.core.db import _SessionDep


CurrentUser = Annotated[UserInDB, Depends(LoginAndJWT.get_current_active_user)]

def addToDB(table: any, session: _SessionDep)-> None:
    session.add(table)
    session.commit()
    session.refresh(table)

def require_admin(user: CurrentUser):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso permitido apenas para administradores"
        )

    return user

AdminUser = Annotated[CurrentUser, Depends(require_admin)]