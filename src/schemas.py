from typing import Optional

from pydantic import BaseModel

class User(BaseModel):
    username: str
    email: str
    password: str

class ShowUser(BaseModel):
    username: str
    email: str

    class Config:
        orm_mode = True

class LoginSchema(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None