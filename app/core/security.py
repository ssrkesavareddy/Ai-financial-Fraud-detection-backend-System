from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import hashlib

from app.core.config import SECRET_KEY
from app.core.database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

ALGORITHM = "HS256"


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)


def hash_text(text: str):
    return hashlib.sha256(text.encode()).hexdigest()


def verify_text(plain: str, hashed: str):
    return hashlib.sha256(plain.encode()).hexdigest() == hashed


def create_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=8)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_activation_token(email: str):
    return create_token({"sub": email, "type": "activation"})


def create_reset_token(email: str):
    return create_token({"sub": email, "type": "reset"})


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from models.user import User

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        token_role = payload.get("role")
        if not email:
            raise HTTPException(401, "Invalid token")
    except Exception:
        raise HTTPException(401, "Invalid token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, "User not found")

    if user.role != token_role:
        raise HTTPException(403, "Role mismatch – possible token tampering")

    return user


def require_role(required_roles: list[str]):
    def role_checker(user=Depends(get_current_user)):
        if user.role not in required_roles:
            raise HTTPException(403, "Access denied")
        return user

    return role_checker