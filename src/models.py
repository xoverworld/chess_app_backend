from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime
from src.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String)
    username = Column(String)
    password = Column(String)
    created_at = Column(DateTime, default=datetime.now)