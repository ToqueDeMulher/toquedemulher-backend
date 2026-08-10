from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _get_engine():
    """Cria o engine lazy — só é chamado quando get_db() é invocado pela primeira vez."""
    url = settings.database_url
    options = settings.db_engine_options
    return create_engine(url, **options)


# Engine singleton: criado na primeira chamada, reutilizado nas demais.
_engine = None
_SessionFactory = None


def _get_session_factory():
    global _engine, _SessionFactory
    if _SessionFactory is None:
        _engine = _get_engine()
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _SessionFactory


def get_db() -> Generator[Session, None, None]:
    SessionLocal = _get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
