from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.openapi.models import OAuth2
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import src.models as models
from src.schemas import User, LoginSchema
from src.database import engine, SessionLocal
from src.services.hashing import Hash
from src.services.oauth2 import get_current_user
from src.services.token import create_access_token

app = FastAPI()


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


@app.post("/register")
async def register(request: User,db: Session = Depends(get_db)):
    new_user = models.User(username=request.username,email=request.email,password=Hash.encrypt(request.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/login")
async def login(request: OAuth2PasswordRequestForm = Depends(),db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.username).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incorrect email or password")
    if not Hash.verify(request.password, user.password):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incorrect email or password")
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=timedelta(minutes=15)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/me")
async def test(db: Session = Depends(get_db), current_user:User = Depends(get_current_user)):
    return current_user