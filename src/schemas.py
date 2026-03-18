from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel

class User(BaseModel):
    username: str
    email: str
    password: str

class UserSchema(BaseModel):
    id: str
    username: str
    email: str
    password: str
    class Config:
        orm_mode = True

class Game(BaseModel):

    white_username: str
    black_username: str
    game_mode: str

    status: str

    winner_color: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class ShowUser(BaseModel):
    username: str
    email: str
    elo: int
    games_played: int
    wins: int
    losses: int
    draws: int
    created_at: datetime
    all_games: List[Game]

    class Config:
        orm_mode = True

class AuthShowUser(BaseModel):
    token: str
    user: ShowUser


class LoginSchema(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None