from pydantic import BaseModel, EmailStr
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserBase(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserInDBBase(UserBase):
    id: Optional[int] = None
    hashed_password: str

    class Config:
        from_attributes = True # Updated from orm_mode

class User(UserInDBBase):
    pass

class UserInDB(UserInDBBase):
    pass
