from typing import Annotated
from fastapi import Depends
from app.models.user import UserInDB
from app.services.loginService import LoginAndJWT
from app.core.db import _SessionDep

CurrentUser = Annotated[UserInDB, Depends(LoginAndJWT.get_current_active_user)]

def addToDB(table: any, session: _SessionDep)-> None:
    session.add(table)
    session.commit()
    session.refresh(table)