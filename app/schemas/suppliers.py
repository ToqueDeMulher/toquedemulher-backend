from typing import Optional
from pydantic import BaseModel, EmailStr

class SupplierRequest(BaseModel):
    name: str
    contact: Optional[str] = None
    email: Optional[EmailStr] = None


class SupplierUpdateRequest(BaseModel):
    supplier_name: str
    name: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[EmailStr] = None