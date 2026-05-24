from typing import Optional
from pydantic import BaseModel

class DescriptionRequest(BaseModel):
    text: str
    usage_tips: Optional[str] = None
    ingredients: Optional[str] = None