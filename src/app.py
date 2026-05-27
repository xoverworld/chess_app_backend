from datetime import timedelta
import time
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.openapi.models import OAuth2
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from starlette.middleware.cors import CORSMiddleware

import src.models as models
from src.schemas import User, LoginSchema, ShowUser, UserSchema, AuthShowUser, BotMoveRequest
from src.database import engine, SessionLocal
from src.services.hashing import Hash
from src.services.oauth2 import get_current_user, get_current_user_ws
from src.services.token import create_access_token
from fastapi import WebSocket, WebSocketDisconnect
from src.services.connectionManager import manager

import chess
import chess.engine
import os

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

        
STOCKFISH_PATH = os.path.join(os.getcwd(), "stockfish", "stockfish-windows-x86-64-avx512icl.exe")

@app.post("/api/bot-move")
async def get_bot_move(request: BotMoveRequest):
    board = chess.Board(request.fen)
    
    # Start the engine
    with chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH) as engine:
        limit = chess.engine.Limit(time=0.1, depth=request.difficulty * 2)
        
        result = engine.play(board, limit)
        best_move = str(result.move) 
        
        from_square = best_move[:2]
        to_square = best_move[2:4]
        promotion = best_move[4:] if len(best_move) > 4 else None

        return {"from": from_square, "to": to_square, "promotion": promotion}
    
@app.post("/register", response_model=AuthShowUser)
async def register(request: User,db: Session = Depends(get_db)):
    new_user = models.User(username=request.username,email=request.email,password=Hash.encrypt(request.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return { "token" : create_access_token(data={"sub": new_user.email}, expires_delta=timedelta(minutes=15)), "user":new_user }

@app.post("/login", response_model=AuthShowUser)
async def login(request: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
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
    #     return { "token" : create_access_token(data={"sub": user2.email}, expires_delta=timedelta(minutes=15)), "user":user2 }
        return {"token": create_access_token(data={"sub": user2.email}), "user": user2}

    # return { "token" : create_access_token(data={"sub": user1.email}, expires_delta=timedelta(minutes=15)), "user":user1 }
    return {"token": create_access_token(data={"sub": user1.email}), "user": user1}

@app.get("/me", response_model=ShowUser)
async def test(db: Session = Depends(get_db), current_user:User = Depends(get_current_user)):
    user = db.query(models.User).filter(models.User.email == current_user.email).first()
    return user

def update_player_stats(db: Session, game: models.Game):
    # Fetch both users from the database
    white_player = db.query(models.User).filter(models.User.id == game.white_id).first()
    black_player = db.query(models.User).filter(models.User.id == game.black_id).first()

    # 1. Update total games played
    if white_player: white_player.games_played += 1
    if black_player: black_player.games_played += 1

    # 2. Update Wins, Losses, Draws, and Elo
    if game.status == "draw":
        if white_player: white_player.draws += 1
        if black_player: black_player.draws += 1
    else: 
        # Someone won (Checkmate or Resignation)
        # We check for both "white" and "w" just to be safe based on what React sends
        winner_is_white = game.winner_color in ["white", "w"]

        if winner_is_white:
            if white_player: white_player.wins += 1
            if black_player: black_player.losses += 1
            
            # Only update Elo if it's a ranked online game
            if game.game_mode == "online": 
                if white_player: white_player.elo += 15
                if black_player: black_player.elo = max(0, black_player.elo - 15) # Prevent negative Elo
        else:
            if black_player: black_player.wins += 1
            if white_player: white_player.losses += 1
            
            if game.game_mode == "online":
                if black_player: black_player.elo += 15
                if white_player: white_player.elo = max(0, white_player.elo - 15)

    db.commit()


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, color:str = None, time_limit: int = 600, db: Session = Depends(get_db)):

    await manager.connect(websocket, room_id)

    if room_id not in manager.game_states:
        manager.game_states[room_id] = {
            "white_time": float(time_limit),
            "black_time": float(time_limit),
            "last_move_time": None, # Starts on the very first move
            "unlimited": time_limit == 0
        }

    state = manager.game_states[room_id]

    try:
        while True:
            data = await websocket.receive_json()
            now = time.time()

            # --- 1. HANDLE TIMEOUT CLAIMS ---
            if data.get("type") == "timeout":
                if not state["unlimited"] and state["last_move_time"] is not None:
                    elapsed = now - state["last_move_time"]
                    turn_color = data.get("turnColor") # The person whose time ran out
                    
                    if turn_color in ["white", "w"]:
                        state["white_time"] -= elapsed
                    else:
                        state["black_time"] -= elapsed

                    # Verify they actually flagged (with a 2-second grace window for network lag)
                    if (turn_color in ["white", "w"] and state["white_time"] <= 2) or \
                       (turn_color in ["black", "b"] and state["black_time"] <= 2):
                        
                        game = db.query(models.Game).filter(models.Game.id == room_id).first()
                        if game and game.status == "ongoing":
                            game.status = "timeout"
                            game.winner_color = "black" if turn_color in ["white", "w"] else "white"
                            game.winner_id = game.black_id if game.winner_color == "black" else game.white_id
                            db.commit()
                            update_player_stats(db, game)

                        await manager.broadcast_to_room(room_id, {
                            "type": "game_over",
                            "message": f"Game Over: {'Black' if turn_color in ['white', 'w'] else 'White'} wins on time!",
                            "whiteTime": 0 if turn_color in ["white", "w"] else state["white_time"],
                            "blackTime": 0 if turn_color in ["black", "b"] else state["black_time"]
                        })
                continue # Skip the rest of the loop

            # --- 2. HANDLE NORMAL MOVES ---
            if data.get("type") == "move" or "pgn" in data:
                # Calculate exact time spent on this move
                if not state["unlimited"]:
                    if state["last_move_time"] is not None:
                        elapsed = now - state["last_move_time"]
                        if data.get("turnColor") in ["white", "w"]: # White just moved
                            state["white_time"] -= elapsed
                        else:
                            state["black_time"] -= elapsed
                    
                    # Reset timestamp for the next player
                    state["last_move_time"] = now

                # OVERWRITE frontend clocks with the absolute server truth
                data["whiteTime"] = state["white_time"]
                data["blackTime"] = state["black_time"]

                # Save the move to the DB
                game = db.query(models.Game).filter(models.Game.id == room_id).first()
                if game and game.status == "ongoing":
                    game.pgn = data["pgn"]
                    if data.get("gameOver"):
                        game.status = data.get("gameOverStatus")
                        if game.status == "checkmate":
                            game.winner_color = data.get("turnColor")
                            game.winner_id = game.white_id if data.get("turnColor") in ["white", "w"] else game.black_id
                        update_player_stats(db, game)
                    db.commit()

            # Broadcast to room
            await manager.broadcast_to_room(room_id, data)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        game = db.query(models.Game).filter(models.Game.id == room_id).first()
        
        # If the game was still ongoing and a player left, they resign
        if game and game.status == models.GameStatus.ONGOING and color:
            game.status = models.GameStatus.RESIGN
            print("resign")
            # The winner is the OPPOSITE color of the person who disconnected
            winner_color = "black" if color == "white" else "white"
            game.winner_color = winner_color
            game.winner_id = game.black_id if winner_color == "black" else game.white_id
            
            update_player_stats(db, game)
            
            # Tell the remaining player they won!
            await manager.broadcast_to_room(room_id, {
                "type": "opponent_disconnected", 
                "message": "Opponent abandoned the match. You win!"
            })

@app.websocket("/matchmaking")
async def matchmaking(websocket: WebSocket, current_user: UserSchema = Depends(get_current_user_ws), db: Session = Depends(get_db) ):
    user = db.query(models.User).filter(models.User.email == current_user.email).first()
    await manager.subscribe(websocket, user, db)
    try:
        while True:
            data = await websocket.receive_json()

            # manager.unsubscribe(websocket)


    except WebSocketDisconnect:
        manager.unsubscribe(websocket)

@app.websocket("/friend-game")
async def friend_game(color:str, websocket: WebSocket, current_user: UserSchema = Depends(get_current_user_ws), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == current_user.email).first()
    await manager.create_friend_game(websocket,user,color)
    try:
        while True:
            data = await websocket.receive_json()

    except WebSocketDisconnect:
        manager.delete_friend_game(websocket)

@app.websocket('/join/{inviteCode}')
async def join_friend_game(inviteCode: str, websocket: WebSocket, current_user: UserSchema = Depends(get_current_user_ws), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == current_user.email).first()
    await manager.join_friend_game(websocket,user,inviteCode,db)
    try:
        while True:
            data = await websocket.receive_json()

    except WebSocketDisconnect:
        manager.delete_friend_game(websocket)


@app.get("/game/{game_id}")
async def get_game_info(game_id: str, db: Session = Depends(get_db)):
    game = db.query(models.Game).filter(models.Game.id == game_id).first()
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
        
    return {
        "white_username": game.white_username,
        "black_username": game.black_username,
        "status": game.status,
        "pgn": game.pgn
    }