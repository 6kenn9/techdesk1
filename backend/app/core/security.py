from datetime import timedelta
from typing import Annotated
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from ..models.models import User, now
from .config import JWT_SECRET
from .database import get_db

hasher = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
Db = Annotated[Session, Depends(get_db)]

def fail(status, message):
    raise HTTPException(status, message)

def verify(password, hash_value):
    try:
        return hasher.verify(hash_value, password)
    except (InvalidHashError, VerificationError):
        return False

def token(user):
    return jwt.encode({"sub": str(user.id), "exp": now() + timedelta(hours=8)}, JWT_SECRET, algorithm="HS256")

def get_current_user(db: Db, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials:
        try:
            claims = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"], options={"require": ["sub", "exp"]})
            user = db.get(User, int(claims["sub"]))
            if user and user.is_active:
                return user
        except (jwt.InvalidTokenError, ValueError):
            pass
    fail(401, "Увійдіть до облікового запису.")

Current = Annotated[User, Depends(get_current_user)]

def require_role(*roles):
    def check(user: Current):
        if user.role not in roles:
            fail(403, "Вам недоступна ця дія.")
        return user
    return check

Staff = Annotated[User, Depends(require_role("admin", "master"))]
Admin = Annotated[User, Depends(require_role("admin"))]
