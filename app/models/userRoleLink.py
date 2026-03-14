from uuid import UUID
from sqlmodel import SQLModel, Field
from uuid import UUID
from sqlmodel import Field


class UserRoleLink(SQLModel, table=True):
    user_id: UUID = Field(foreign_key="userindb.id", primary_key=True)
    role_id: int = Field(foreign_key="roleindb.id", primary_key=True)