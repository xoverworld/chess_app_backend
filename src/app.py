from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.openapi.models import OAuth2
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware

import src.models as models
from src.schemas import User, LoginSchema, ShowUser
from src.database import engine, SessionLocal
from src.services.hashing import Hash
from src.services.oauth2 import get_current_user
from src.services.token import create_access_token
from fastapi import WebSocket, WebSocketDisconnect
from src.services.connectionManager import manager

app = FastAPI()
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Allows specific origins
    allow_credentials=True,
    allow_methods=["*"],              # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],              # Allows all headers
)


models.Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
@app.get("/")
async def root():

    return {"data": "Hello World"}


@app.post("/register", response_model=ShowUser)
async def register(request: User,db: Session = Depends(get_db)):
    new_user = models.User(username=request.username,email=request.email,password=Hash.encrypt(request.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return { "token" : create_access_token(data={"sub": new_user.email}, expires_delta=timedelta(minutes=15)), "user":new_user }

@app.post("/login")
async def login(request: OAuth2PasswordRequestForm = Depends(),db: Session = Depends(get_db)):
    user1 = db.query(models.User).filter(models.User.email == request.username).first()
    user2 = db.query(models.User).filter(models.User.username == request.username).first()
    if not user1 and not user2:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incorrect Credentials")

    if not user1:
        if not Hash.verify(request.password, user2.password):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incorrect Credentials")
    if not user2:
        if not Hash.verify(request.password, user1.password):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incorrect Credentials")
    if not user1:
        return { "token" : create_access_token(data={"sub": user2.email}, expires_delta=timedelta(minutes=15)), "user":user2 }
    return { "token" : create_access_token(data={"sub": user1.email}, expires_delta=timedelta(minutes=15)), "user":user1 }

@app.get("/me", response_model=ShowUser)
async def test(db: Session = Depends(get_db), current_user:User = Depends(get_current_user)):
    user = db.query(models.User).filter(models.User.email == current_user.email).first()
    return user


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    # 1. Player connects to the room
    await manager.connect(websocket, room_id)

    try:
        # 2. The Infinite Loop (This keeps the tunnel open forever)
        while True:
            # The server pauses here and waits for this player to send a move
            data = await websocket.receive_json()

            # 3. When a move is received, broadcast it to the room
            await manager.broadcast_to_room(room_id, data)

    except WebSocketDisconnect:
        # 4. If the player closes the tab, this exception is triggered
        manager.disconnect(websocket, room_id)

@app.websocket("/matchmaking")
async def matchmaking(websocket: WebSocket):
    await manager.subscribe(websocket)
    try:
        while True:
            data = await websocket.receive_json()


    except WebSocketDisconnect:
        manager.unsubscribe(websocket)