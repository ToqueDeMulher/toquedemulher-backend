from typing import Optional
from pydantic import BaseModel, Field

class ProductImageRequest(BaseModel):
    url: str
    order: int = Field(ge=1)
    alt_text: Optional[str] = None

class ProductImageResponse(BaseModel):
    id: int
    url: str
    order: int = Field(ge=1)
    alt_text: Optional[str] = None