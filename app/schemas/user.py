from datetime import date
from typing import Optional
from pydantic import BaseModel, EmailStr

class GetUserResponse(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    cpf: Optional[str] = None
    email: EmailStr 
    phone: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    accepts_marketing: Optional[bool] = None
    role: Optional[str] = None

class UserRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class ChangeUserInformationRequest(BaseModel):
    name: Optional[str] = None
    cpf: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    accepts_marketing: Optional[bool] = None


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class DeleteAccountRequest(BaseModel):
    current_password: str
    confirm_text: str

class Token (BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class Login(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class GoogleLoginRequest(BaseModel):
    credential: str
