from pydantic import BaseModel, EmailStr

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    first_name: str = ""
    last_name: str = ""

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserInfo(BaseModel):
    id: int
    email: EmailStr
    first_name: str = ""
    last_name: str = ""

class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo