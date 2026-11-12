import secrets
from datetime import timedelta
from fastapi import APIRouter, Request
from sqlalchemy import func, select
from ..core.config import DEMO_MODE, GOOGLE_CLIENT_ID
from ..core.security import Admin, Current, Db, RateLimiter, Staff, client_ip, fail, hasher, throttle, token, verify
from ..models.models import Order, User, now
from ..schemas.schemas import GoogleLogin, Login, PasswordChange, Registration, StaffRegistration, TelegramNotifications, UserEdit
from ..services.domain import ACTIVE, public_user

router = APIRouter(prefix="/api")
login_failures = RateLimiter(limit=5, window=300)
registrations = RateLimiter(limit=10, window=3600)
password_changes = RateLimiter(limit=10, window=900)

def create_account(db, payload, role="client", specialization=""):
    email = payload.email.lower()
    if db.scalar(select(User.id).where((User.email == email) | (User.phone == payload.phone))):
        fail(409, "Ця електронна пошта або телефон уже зареєстровані.")
    user = User(full_name=payload.full_name, email=email, phone=payload.phone,
                role=role, specialization=specialization, password_hash=hasher.hash(payload.password))
    db.add(user)
    db.commit()
    return user

@router.get("/auth/options")
def auth_options():
    from ..services import telegram
    return {"demo_mode": DEMO_MODE, "telegram": telegram.bot is not None,
            "google_client_id": GOOGLE_CLIENT_ID or None}

@router.post("/auth/register", status_code=201, dependencies=[throttle(registrations, "register")])
def register(payload: Registration, db: Db):
    user = create_account(db, payload)
    return {"access_token": token(user), "user": public_user(user)}

@router.post("/auth/login")
def login(payload: Login, db: Db, request: Request):
    key = (client_ip(request), payload.email.lower())
    if login_failures.blocked(key):
        fail(429, "Забагато невдалих спроб входу. Спробуйте через 5 хвилин.")
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify(payload.password, user.password_hash):
        login_failures.hit(key)
        fail(401, "Неправильна електронна пошта або пароль.")
    login_failures.reset(key)
    return {"access_token": token(user), "user": public_user(user)}

@router.post("/auth/google")
def google_login(payload: GoogleLogin, db: Db, request: Request):
    """Вхід через Google. Відомий e-mail — вхід в існуючий кабінет; новий — реєстрація клієнта,
    для якої потрібен телефон (Google його не повідомляє)."""
    from ..services import google
    if not GOOGLE_CLIENT_ID:
        fail(503, "Вхід через Google не налаштовано на сервері.")
    key = (client_ip(request), "google")
    if login_failures.blocked(key):
        fail(429, "Забагато невдалих спроб входу. Спробуйте через 5 хвилин.")
    try:
        claims = google.verify_credential(payload.credential)
    except Exception:
        login_failures.hit(key)
        fail(401, "Google не підтвердив вхід. Спробуйте ще раз.")
    email = claims["email"].lower()
    user = db.scalar(select(User).where(User.email == email))
    if user:
        if not user.is_active:
            fail(401, "Обліковий запис вимкнено адміністратором.")
    else:
        if not payload.phone:
            return {"needs_phone": True, "email": email, "full_name": claims.get("name") or email.split("@")[0]}
        if db.scalar(select(User.id).where(User.phone == payload.phone)):
            fail(409, "Цей телефон уже зареєстровано.")
        user = User(full_name=(claims.get("name") or email.split("@")[0])[:150], email=email, phone=payload.phone,
                    role="client", password_hash=hasher.hash(secrets.token_urlsafe(32)))
        db.add(user)
        db.commit()
    return {"access_token": token(user), "user": public_user(user)}

@router.get("/auth/me")
def me(user: Current):
    return public_user(user)

@router.post("/auth/telegram-link")
def telegram_link(db: Db, user: Current):
    from ..services import telegram
    if not telegram.bot:
        fail(503, "Telegram-бот не налаштовано на сервері.")
    user.telegram_link_code = secrets.token_urlsafe(16)
    user.telegram_link_expires_at = now() + timedelta(minutes=15)
    db.commit()
    return {"url": f"https://t.me/{telegram.bot.username}?start={user.telegram_link_code}", "expires_in": 900}

ROLE_NAMES = {"client": "клієнт", "master": "майстер", "admin": "адміністратор"}

@router.post("/auth/telegram-test")
def telegram_test(user: Current):
    """Тестове повідомлення: показує, до якого облікового запису прив’язано цей чат."""
    from ..services import telegram
    if not telegram.bot:
        fail(503, "Telegram-бот не налаштовано на сервері.")
    if user.telegram_chat_id is None:
        fail(409, "Спершу підключіть Telegram.")
    contact = user.email or user.phone
    try:
        telegram.bot.send(user.telegram_chat_id,
                          f"Тестове сповіщення TechDesk.\nОбліковий запис: {user.full_name} ({ROLE_NAMES[user.role]}), {contact}.\n"
                          "Сповіщення для цього облікового запису надходитимуть саме в цей чат.")
    except Exception:
        fail(502, "Telegram не прийняв повідомлення. Можливо, ви заблокували бота — підключіть його знову.")
    return {"sent": True}

@router.delete("/auth/telegram-link")
def telegram_unlink(db: Db, user: Current):
    user.telegram_chat_id = user.telegram_link_code = user.telegram_link_expires_at = None
    user.telegram_muted = False
    db.commit()
    return public_user(user)

@router.put("/auth/telegram-notifications")
def telegram_notifications(payload: TelegramNotifications, db: Db, user: Current):
    """Увімкнути або призупинити сповіщення, не відв'язуючи чат."""
    if user.telegram_chat_id is None:
        fail(409, "Спершу підключіть Telegram.")
    user.telegram_muted = not payload.enabled
    db.commit()
    return public_user(user)

@router.get("/users")
def users(db: Db, user: Staff, role: str | None = None):
    query = select(User).order_by(User.full_name)
    if role:
        query = query.where(User.role == role)
    if user.role != "admin":
        query = query.where(User.role != "admin", User.is_active.is_(True))
    workload = dict(db.execute(select(Order.master_id, func.count(Order.id))
                               .where(Order.status.in_(ACTIVE)).group_by(Order.master_id)).all())
    return [dict(public_user(item), active_orders=workload.get(item.id, 0)) for item in db.scalars(query)]

@router.post("/users", status_code=201)
def add_user(payload: StaffRegistration, db: Db, user: Admin):
    return public_user(create_account(db, payload, payload.role, payload.specialization))

@router.patch("/users/{user_id}")
def edit_user(user_id: int, payload: UserEdit, db: Db, user: Admin):
    target = db.get(User, user_id)
    if not target:
        fail(404, "Користувача не знайдено.")
    if user.id == target.id and not payload.is_active:
        fail(409, "Ви не можете вимкнути власний обліковий запис.")
    target.is_active = payload.is_active
    target.specialization = payload.specialization
    db.commit()
    return public_user(target)

@router.post("/auth/password", dependencies=[throttle(password_changes, "password")])
def change_password(payload: PasswordChange, db: Db, user: Current):
    """Зміна власного пароля. Інші сеанси користувача завершуються, поточний отримує новий токен."""
    if user.email is None:
        fail(409, "Спершу завершіть реєстрацію: вкажіть пошту й пароль у кабінеті.")
    if not verify(payload.current_password, user.password_hash):
        fail(400, "Поточний пароль указано неправильно.")
    if payload.new_password == payload.current_password:
        fail(422, "Новий пароль має відрізнятися від поточного.")
    user.password_hash = hasher.hash(payload.new_password)
    user.token_version = (user.token_version or 0) + 1
    user.must_change_password = False
    db.commit()
    return {"access_token": token(user), "user": public_user(user)}

def temporary_password():
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # без схожих символів l/1, o/0
    return "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3))

@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, db: Db, admin: Admin):
    """Адміністратор видає тимчасовий пароль; усі сеанси користувача завершуються."""
    target = db.get(User, user_id)
    if not target:
        fail(404, "Користувача не знайдено.")
    if target.id == admin.id:
        fail(409, "Власний пароль змініть у профілі.")
    if target.email is None:
        fail(409, "Гостьовий кабінет не має пароля: видайте клієнту нове особисте посилання.")
    password = temporary_password()
    target.password_hash = hasher.hash(password)
    target.token_version = (target.token_version or 0) + 1
    target.must_change_password = True
    db.commit()
    return {"temporary_password": password, "user": public_user(target)}

@router.post("/users/{user_id}/claim-link")
def reissue_claim(user_id: int, db: Db, admin: Admin):
    """Нове особисте посилання для гостьового кабінету, якщо клієнт загубив старе або воно застаріло."""
    from .intake import CLAIM_DAYS, issue_claim
    target = db.get(User, user_id)
    if not target:
        fail(404, "Користувача не знайдено.")
    if target.email is not None:
        fail(409, "Обліковий запис уже має пошту й пароль: скористайтеся скиданням пароля.")
    if not target.is_active:
        fail(409, "Спершу увімкніть обліковий запис.")
    raw = issue_claim(target)
    db.commit()
    return {"claim_token": raw, "claim_days": CLAIM_DAYS, "user": public_user(target)}
