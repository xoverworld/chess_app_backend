from typing import Annotated

from fastapi import Depends, HTTPException, status, WebSocketException
from fastapi.security import OAuth2PasswordBearer
from starlette.websockets import WebSocket
from src.services.token import verify_token, verify_token_ws


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    return verify_token(token, credentials_exception)

async def get_current_user_ws(websocket: WebSocket):
    token = websocket.query_params.get("token")

    credentials_exception = WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
    if not token:
        raise credentials_exception
        # await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return verify_token_ws(token, credentials_exception)