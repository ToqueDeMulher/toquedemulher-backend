from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr

class UserResponse(BaseModel):
    message: str

class UserRequest(BaseModel):
    email: EmailStr
    password: str

class ChangeUserInformationRequest(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None


    

class Token (BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class Login(BaseModel):
    email: str
    password: str