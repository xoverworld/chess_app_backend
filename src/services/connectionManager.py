from fastapi import WebSocket
from src.schemas import UserSchema
from src import models
import random


class ConnectionManager:
    def __init__(self):
        # This dictionary will map a room_id to a list of connected WebSockets
        # Example: {"room_123": [PlayerA_Socket, PlayerB_Socket]}
        self.active_rooms: dict[str, list[WebSocket]] = {}
        self.matchmaking_queue: list[dict] = []

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
        await websocket.accept()  # "Pick up the phone"

        # If the room doesn't exist yet, create it
        if room_id not in self.active_rooms:
            self.active_rooms[room_id] = []

        # Add this player's connection to the room
        self.active_rooms[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        # Remove the player when they close the browser
        if room_id in self.active_rooms:
            self.active_rooms[room_id].remove(websocket)
            # If the room is empty, delete it to save memory
            if len(self.active_rooms[room_id]) == 0:
                del self.active_rooms[room_id]

    async def broadcast_to_room(self, room_id: str, message: dict):
        # Send the chess move to everyone currently in this specific room
        if room_id in self.active_rooms:
            for connection in self.active_rooms[room_id]:
                await connection.send_json(message)


# Create a single instance of this manager to use across your app
manager = ConnectionManager()