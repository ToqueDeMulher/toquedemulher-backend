from app.core.db import Database


engine = Database.engine
create_db_and_tables = Database.create_db_and_tables
get_session = Database.get_session


__all__ = [
    "engine",
    "create_db_and_tables",
    "get_session",
]
