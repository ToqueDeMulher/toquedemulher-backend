from pydantic import BaseModel, EmailStr

class UserResponse(BaseModel):
    message: str

class UserRequest(BaseModel):
    name: str
    cpf:str
    email: EmailStr
    password: str

class Token (BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class Login(BaseModel):
    email: str
    password: str