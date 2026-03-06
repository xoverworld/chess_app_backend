from passlib.context import CryptContext
import bcrypt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class Hash:
    def encrypt(password: str):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    def verify(password: str, hashedPassword: str):
        return bcrypt.checkpw(password.encode('utf-8'), hashedPassword.encode('utf-8'))