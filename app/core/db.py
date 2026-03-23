from typing import Annotated
from sqlmodel import SQLModel, create_engine, Session
from app.core.settings import settings

from fastapi import Depends


class Database:

    engine = create_engine(settings.DATABASE_URL, echo=True) 

    @staticmethod
    def create_db_and_tables():
        SQLModel.metadata.create_all(Database.engine)

    @staticmethod
    def get_session():
        with Session(Database.engine) as session:
            yield session
    
    @staticmethod
    def SessionLocal() -> Session:
        return Session(Database.engine)


_SessionDep = Annotated[Session, Depends(Database.get_session)]

Database.SessionDep = _SessionDep
