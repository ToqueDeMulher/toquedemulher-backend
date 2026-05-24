from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship

class Description(SQLModel, table=True):
    __tablename__ = "description"

    id: Optional[int] = Field(default=None, primary_key=True)
    text: str
    usage_tips: Optional[str] = None
    ingredients: Optional[str] = None

    products: List["Product"] = Relationship(back_populates="description") #type: ignore