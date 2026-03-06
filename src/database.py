from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from sqlalchemy.ext.declarative import declarative_base
from os import getenv

load_dotenv()

engine = create_engine(getenv("DATABASE_URL"))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()