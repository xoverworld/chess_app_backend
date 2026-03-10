from datetime import timedelta, datetime
from os import getenv
from typing import Optional

from dotenv import load_dotenv
from fastapi import HTTPException
from jose import jwt, JWTError

from src.schemas import TokenData

load_dotenv()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=int(getenv("ACCESS_TOKEN_EXPIRE_MINUTES")))

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, getenv("JWT_SECRET_KEY"), algorithm=getenv("JWT_ALGORITHM"))
    return encoded_jwt

def verify_token(token: str, credentials_exception: Optional[HTTPException] = None):
    try:
        payload = jwt.decode(token, getenv("JWT_SECRET_KEY"))
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)

        return token_data
    except JWTError:
        raise credentials_exception