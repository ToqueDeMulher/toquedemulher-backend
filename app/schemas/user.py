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
    cpf: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None

class ChangeEmailRequest(BaseModel):
    new_email: EmailStr

class ChangePasswordRequest(BaseModel):
    new_password: str

class Token (BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class Login(BaseModel):
    email: str
    password: str