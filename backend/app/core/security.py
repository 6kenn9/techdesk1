from collections import defaultdict, deque
from datetime import timedelta
from threading import Lock
from time import monotonic
from typing import Annotated
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
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
    return jwt.encode({"sub": str(user.id), "ver": user.token_version or 0, "exp": now() + timedelta(hours=8)},
                      JWT_SECRET, algorithm="HS256")

# З тимчасовим паролем від адміністратора доступні лише ці маршрути: дізнатися про себе й задати власний пароль.
TEMPORARY_PASSWORD_PATHS = {"/api/auth/me", "/api/auth/password"}

def get_current_user(db: Db, request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    user = None
    if credentials:
        try:
            claims = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"], options={"require": ["sub", "exp"]})
            found = db.get(User, int(claims["sub"]))
            if found and found.is_active and claims.get("ver", 0) == (found.token_version or 0):
                user = found
        except (jwt.InvalidTokenError, ValueError):
            pass
    if not user:
        fail(401, "Увійдіть до облікового запису.")
    if user.must_change_password and request.url.path not in TEMPORARY_PASSWORD_PATHS:
        fail(403, "Спершу задайте власний пароль у профілі: тимчасовий пароль дає доступ лише до зміни пароля.")
    return user

Current = Annotated[User, Depends(get_current_user)]

def require_role(*roles):
    def check(user: Current):
        if user.role not in roles:
            fail(403, "Вам недоступна ця дія.")
        return user
    return check

Staff = Annotated[User, Depends(require_role("admin", "master"))]
Admin = Annotated[User, Depends(require_role("admin"))]

class RateLimiter:
    """Обмежує кількість подій для ключа (IP, e-mail) у ковзному часовому вікні."""
    def __init__(self, limit, window, clock=monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.events = defaultdict(deque)
        self.lock = Lock()

    def _recent(self, key):
        queue, moment = self.events[key], self.clock()
        while queue and moment - queue[0] >= self.window:
            queue.popleft()
        return queue

    def blocked(self, key):
        with self.lock:
            return len(self._recent(key)) >= self.limit

    def hit(self, key):
        """Реєструє подію; повертає True, якщо ліміт перевищено."""
        with self.lock:
            queue = self._recent(key)
            queue.append(self.clock())
            return len(queue) > self.limit

    def reset(self, key):
        with self.lock:
            self.events.pop(key, None)

def client_ip(request: Request):
    # nginx передає справжню адресу клієнта в X-Real-IP; без проксі береться адреса з'єднання.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")

def throttle(limiter, scope):
    def check(request: Request):
        if limiter.hit((scope, client_ip(request))):
            fail(429, "Забагато запитів. Спробуйте трохи пізніше.")
    return Depends(check)
