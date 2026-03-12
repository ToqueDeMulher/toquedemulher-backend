from typing import Optional
from pydantic import BaseModel, EmailStr

class SupplierRequest(BaseModel):
    name: str
    contact: Optional[str] = None
    email: Optional[EmailStr] = None
