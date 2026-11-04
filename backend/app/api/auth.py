from fastapi import APIRouter
from sqlalchemy import func, select
from ..core.config import DEMO_MODE
from ..core.security import Admin, Current, Db, Staff, fail, hasher, token, verify
from ..models.models import Order, User
from ..schemas.schemas import Login, Registration, StaffRegistration, UserEdit
from ..services.domain import ACTIVE, public_user

router = APIRouter(prefix="/api")

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
    return {"demo_mode": DEMO_MODE}

@router.post("/auth/register", status_code=201)
def register(payload: Registration, db: Db):
    user = create_account(db, payload)
    return {"access_token": token(user), "user": public_user(user)}

@router.post("/auth/login")
def login(payload: Login, db: Db):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify(payload.password, user.password_hash):
        fail(401, "Неправильна електронна пошта або пароль.")
    return {"access_token": token(user), "user": public_user(user)}

@router.get("/auth/me")
def me(user: Current):
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
