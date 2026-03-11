from fastapi import WebSocket
import uuid


class ConnectionManager:
    def __init__(self):
        # This dictionary will map a room_id to a list of connected WebSockets
        # Example: {"room_123": [PlayerA_Socket, PlayerB_Socket]}
        self.active_rooms: dict[str, list[WebSocket]] = {}
        self.matchmaking_queue: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()  # "Pick up the phone"

        # If the room doesn't exist yet, create it
        if room_id not in self.active_rooms:
            self.active_rooms[room_id] = []

        # Add this player's connection to the room
        self.active_rooms[room_id].append(websocket)

    async def subscribe(self, websocket: WebSocket):
        await websocket.accept()
        if len(self.matchmaking_queue) > 0:
            opponent_socket = self.matchmaking_queue.pop(0)

            room_id = str(uuid.uuid4())

            match_data1 = {"type": "match_found", "gameId": room_id, "reversed": False}
            match_data2 = {"type": "match_found", "gameId": room_id, "reversed": True}
            await opponent_socket.send_json(match_data1)
            await websocket.send_json(match_data2)
        else:
            self.matchmaking_queue.append(websocket)
            await websocket.send_json({"type": "waiting", "message": "Looking for opponent..."})


    def unsubscribe(self, websocket: WebSocket):
        if websocket in self.matchmaking_queue:
            self.matchmaking_queue.remove(websocket)

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