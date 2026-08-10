from typing import Annotated

from fastapi import Depends
from sqlmodel import SQLModel, Session, create_engine

from app.core.settings import settings
import app.models  # noqa: F401


class Database:
    engine = create_engine(settings.database_url, **settings.db_engine_options)

    @staticmethod
    def create_db_and_tables():
        SQLModel.metadata.create_all(Database.engine)

    @staticmethod
    def get_session():
        with Session(Database.engine) as session:
            yield session


_SessionDep = Annotated[Session, Depends(Database.get_session)]

Database.SessionDep = _SessionDep
