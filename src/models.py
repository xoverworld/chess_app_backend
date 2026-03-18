from datetime import datetime
import uuid
import enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from src.database import Base


# Helper function to ensure every row gets a unique string UUID
def generate_uuid():
    return str(uuid.uuid4())

class GameMode(str, enum.Enum):
    ONLINE = "online"
    FRIEND = "friend"
    BOT = "bot"

class GameStatus(str, enum.Enum):
    ONGOING = "ongoing"
    CHECKMATE = "checkmate"
    DRAW = "draw"
    RESIGN = "resign"
    TIMEOUT = "timeout"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    elo = Column(Integer, nullable=False, default=800)
    games_played = Column(Integer, nullable=False, default=0)
    wins = Column(Integer, nullable=False, default=0)
    losses = Column(Integer, nullable=False, default=0)
    draws = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    games_as_white = relationship("Game", foreign_keys="[Game.white_id]", back_populates="white_player")
    games_as_black = relationship("Game", foreign_keys="[Game.black_id]", back_populates="black_player")

    @property
    def all_games(self):
        return self.games_as_white + self.games_as_black


class Game(Base):
    __tablename__ = "games"

    id = Column(String, primary_key=True, default=generate_uuid)

    white_id = Column(String, ForeignKey("users.id"), nullable=True)
    black_id = Column(String, ForeignKey("users.id"), nullable=True)

    white_username = Column(String, nullable=False)
    black_username = Column(String, nullable=False)
    game_mode = Column(Enum(GameMode), nullable=False, default=GameMode.ONLINE)

    pgn = Column(Text, nullable=True)
    status = Column(Enum(GameStatus), default=GameStatus.ONGOING, nullable=False)

    winner_id = Column(String, ForeignKey("users.id"), nullable=True)
    winner_color = Column(String, nullable=True)  # 'w' or 'b'
    created_at = Column(DateTime, nullable=False, default=datetime.now)

    white_player = relationship("User", foreign_keys=[white_id], back_populates="games_as_white")
    black_player = relationship("User", foreign_keys=[black_id], back_populates="games_as_black")
    winner = relationship("User", foreign_keys=[winner_id])