from fastapi import WebSocket, WebSocketException, status
from src.schemas import UserSchema
from src import models
import random
import uuid


class ConnectionManager:
    def __init__(self):
        self.active_rooms: dict[str, list[WebSocket]] = {}
        self.matchmaking_queue: list[dict] = []
        self.friend_game: list[dict] = []

        self.game_states: dict[str, dict] = {}

    async def create_friend_game(self, websocket: WebSocket, user: UserSchema, color: str):
        await websocket.accept()
        invite_code = str(uuid.uuid4())[:7]
        print(invite_code)
        self.friend_game.append({"websocket":websocket, "user":user, "inviteCode":invite_code, "color": color})
        await websocket.send_json({"type":"waiting", "inviteCode": invite_code})

    async def join_friend_game(self, websocket: WebSocket, user: UserSchema, invite_code: str, db):
        await websocket.accept()
        checkCode = False
        for game in self.friend_game:
            if invite_code == game["inviteCode"] and user.id != game["user"].id:
                checkCode = True
                
                opponent_socket = game["websocket"]
                opponent_user = game["user"]

                opponent_is_white = game["color"] == "white"
                if opponent_is_white:
                    white_player_id = opponent_user.id
                    black_player_id = user.id
                    white_player_username = opponent_user.username
                    black_player_username = user.username
                else:
                    white_player_id = user.id
                    black_player_id = opponent_user.id
                    white_player_username = user.username
                    black_player_username = opponent_user.username

                game = models.Game(white_id=white_player_id, black_id=black_player_id, white_username=white_player_username, black_username=black_player_username, game_mode=models.GameMode.FRIEND)

                db.add(game)
                db.commit()
                db.refresh(game)
                await websocket.send_json({"type": "match_found", "gameId": game.id, "color": "black" if opponent_is_white else "white"})
                await opponent_socket.send_json({"type": "match_found", "gameId": game.id, "color": "white" if opponent_is_white else "black"})

        if checkCode == False:
            await websocket.send_json({"data":"Game not found", "type":"error"})

    def delete_friend_game(self, websocket: WebSocket):
        self.friend_game = [
            item for item in self.friend_game
            if item["websocket"] != websocket
        ]

    async def subscribe(self, websocket: WebSocket, user: UserSchema,  db):
        await websocket.accept()
        if len(self.matchmaking_queue) > 0:
            if self.matchmaking_queue[0]["user"].id != user.id:
                opponent_data = self.matchmaking_queue.pop(0)
                opponent_socket = opponent_data["websocket"]
                opponent_user = opponent_data["user"]

                opponent_is_white = random.choice([True, False])
                if opponent_is_white:
                    white_player_id = opponent_user.id
                    black_player_id = user.id
                    white_player_username = opponent_user.username
                    black_player_username = user.username
                else:
                    white_player_id = user.id
                    black_player_id = opponent_user.id
                    white_player_username = user.username
                    black_player_username = opponent_user.username

                game = models.Game(white_id=white_player_id, black_id=black_player_id, white_username=white_player_username, black_username=black_player_username)

                db.add(game)
                db.commit()
                db.refresh(game)

                match_data1 = {"type": "match_found", "gameId": game.id, "color": "white"}
                match_data2 = {"type": "match_found", "gameId": game.id, "color": "black"}
                if opponent_is_white:
                    await opponent_socket.send_json(match_data1)
                    await websocket.send_json(match_data2)
                else:
                    await opponent_socket.send_json(match_data2)
                    await websocket.send_json(match_data1)
            else:
                await websocket.send_json({"type": "waiting", "message": "Already in queue"})
        else:
            self.matchmaking_queue.append({"websocket":websocket, "user":user})
            await websocket.send_json({"type": "waiting", "message": "Looking for opponent..."})


    def unsubscribe(self, websocket: WebSocket):
        self.matchmaking_queue = [
            item for item in self.matchmaking_queue
            if item["websocket"] != websocket
        ]

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()

        if room_id not in self.active_rooms:
            self.active_rooms[room_id] = []

        self.active_rooms[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_rooms:
            self.active_rooms[room_id].remove(websocket)

            if len(self.active_rooms[room_id]) == 0:
                del self.active_rooms[room_id]

    async def broadcast_to_room(self, room_id: str, message: dict):
        if room_id in self.active_rooms:
            for connection in self.active_rooms[room_id]:
                await connection.send_json(message)


manager = ConnectionManager()