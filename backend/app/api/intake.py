"""Швидке оформлення: заявка без реєстрації, приймання працівником за телефоном, підказки моделей."""
import secrets
from datetime import timedelta
from hashlib import sha256
from fastapi import APIRouter, Query
from sqlalchemy import func, select
from ..core.security import Current, Db, RateLimiter, Staff, client_ip, fail, hasher, throttle, token
from ..models.models import Device, ModelPreset, User, now
from ..schemas.schemas import Claim, CompleteRegistration, Intake, QuickRequest, SerialInput
from ..services.domain import PUBLIC_REFUSAL, access_device, change_identity, add_preset, new_order, order_details, public_user, warranty
from .orders import validate_master

router = APIRouter(prefix="/api")
quick_requests = RateLimiter(limit=5, window=3600)
claims = RateLimiter(limit=20, window=900)
CLAIM_DAYS = 30

def digest(value):
    return sha256(value.encode()).hexdigest()

def issue_claim(user):
    raw = secrets.token_urlsafe(24)
    user.claim_token_hash = digest(raw)
    user.claim_expires_at = now() + timedelta(days=CLAIM_DAYS)
    return raw

def find_or_create_client(db, phone, full_name, public=False):
    """Повертає (клієнт, claim-токен). Токен видається лише для щойно створеного гостьового кабінету."""
    client = db.scalar(select(User).where(User.phone == phone).with_for_update())
    if client:
        if client.role != "client" or not client.is_active:
            fail(409, PUBLIC_REFUSAL if public else "Цей телефон не можна використати для заявки клієнта.")
        return client, None
    client = User(full_name=(full_name or "Клієнт").strip(), email=None, phone=phone, role="client",
                  password_hash=hasher.hash(secrets.token_urlsafe(32)))
    db.add(client)
    db.flush()
    return client, issue_claim(client)

def with_preset_specs(db, data):
    """Клієнт не вводить характеристики: якщо модель є в довіднику, паспорт заповнюється з нього."""
    if not data.get("specifications"):
        preset = db.scalar(select(ModelPreset).where(
            ModelPreset.device_category == data["device_category"],
            func.lower(ModelPreset.brand) == data["brand"].lower(),
            func.lower(ModelPreset.model_name) == data["model"].lower()))
        if preset:
            data["specifications"] = dict(preset.default_specs)
    return data

def register_device(db, owner, data, public=False):
    """public — публічна форма: відповідь не має розкривати, що такий серійний номер уже є в базі."""
    data = with_preset_specs(db, dict(data))
    if data.get("serial_number"):
        existing = db.scalar(select(Device).where(Device.serial_number == data["serial_number"]))
        if existing:
            if existing.owner_id != owner.id:
                fail(409, PUBLIC_REFUSAL if public else "Пристрій із таким серійним номером уже є в системі. Зверніться до працівника центру.")
            return existing
    device = Device(owner_id=owner.id, **data)
    db.add(device)
    db.flush()
    return device

@router.get("/public/models")
def public_models(db: Db, q: str = Query("", max_length=80), category: str = Query("", max_length=40)):
    """Підказки моделей для автодоповнення: без характеристик і без авторизації."""
    query = select(ModelPreset)
    if category:
        query = query.where(ModelPreset.device_category == category)
    title = ModelPreset.brand + " " + ModelPreset.model_name
    for word in q.split()[:6]:  # кожне слово окремо: «legion 5», «5 legion» і «LEGION» знаходять ту саму модель
        query = query.where(title.icontains(word, autoescape=True))
    presets = db.scalars(query.order_by(ModelPreset.brand, ModelPreset.model_name).limit(20))
    return [{"device_category": item.device_category, "brand": item.brand, "model": item.model_name} for item in presets]

@router.get("/passports/spec-suggestion")
def spec_suggestion(db: Db, user: Staff, category: str = Query(max_length=40), brand: str = Query(max_length=80),
                    model: str = Query(max_length=120)):
    """Характеристики для нового паспорта: спершу з довідника моделей, інакше з такого самого пристрою в базі."""
    brand, model = brand.strip(), model.strip()
    preset = db.scalar(select(ModelPreset).where(
        ModelPreset.device_category == category, func.lower(ModelPreset.brand) == brand.lower(),
        func.lower(ModelPreset.model_name) == model.lower()))
    if preset:
        return {"source": "preset", "specifications": dict(preset.default_specs)}
    similar = db.scalars(select(Device).where(
        Device.device_category == category, func.lower(Device.brand) == brand.lower(),
        func.lower(Device.model) == model.lower()).order_by(Device.updated_at.desc()))
    for device in similar:
        if device.specifications:
            return {"source": "device", "specifications": dict(device.specifications)}
    return {"source": None, "specifications": {}}

@router.post("/quick-request", status_code=201, dependencies=[throttle(quick_requests, "quick")])
def quick_request(payload: QuickRequest, db: Db):
    if payload.website:  # поле-приманка заповнив бот: вдаємо успіх, нічого не зберігаючи
        return {"order_number": "—", "claim_token": None, "account_exists": False}
    client, claim = find_or_create_client(db, payload.phone, payload.full_name, public=True)
    device = register_device(db, client, payload.device.model_dump(), public=True)
    order = new_order(db, client, device, {"problem_description": payload.problem_description,
                                             "delivery": payload.delivery.model_dump() if payload.delivery else None}, public=True)
    db.commit()
    return {"order_number": order.order_number, "order_id": order.id, "claim_token": claim,
            "account_exists": claim is None, "claim_days": CLAIM_DAYS}

@router.post("/auth/claim", dependencies=[throttle(claims, "claim")])
def claim(payload: Claim, db: Db):
    user = db.scalar(select(User).where(User.claim_token_hash == digest(payload.token)))
    if not user or not user.claim_expires_at or user.claim_expires_at < now() or not user.is_active:
        fail(404, "Посилання недійсне або застаріло. Зверніться до працівника центру.")
    return {"access_token": token(user), "user": public_user(user)}

@router.post("/auth/complete-registration", dependencies=[throttle(claims, "complete")])
def complete_registration(payload: CompleteRegistration, db: Db, user: Current):
    if user.email is not None:
        fail(409, "Обліковий запис уже завершено.")
    email = payload.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        fail(409, "Ця електронна пошта вже зареєстрована.")
    user.email = email
    user.password_hash = hasher.hash(payload.password)
    user.claim_token_hash = user.claim_expires_at = None
    db.commit()
    return public_user(user)

@router.get("/users/lookup")
def lookup_client(db: Db, user: Staff, phone: str = Query(min_length=5, max_length=24)):
    from ..schemas.schemas import normalize_phone
    client = db.scalar(select(User).where(User.phone == normalize_phone(phone), User.role == "client"))
    if not client:
        return None
    devices = db.scalars(select(Device).where(Device.owner_id == client.id).order_by(Device.id.desc()))
    return {"id": client.id, "full_name": client.full_name, "phone": client.phone, "is_guest": client.email is None,
            "devices": [{"id": item.id, "serial_number": item.serial_number, "device_category": item.device_category,
                         "brand": item.brand, "model": item.model} for item in devices]}

@router.post("/orders/intake", status_code=201)
def intake(payload: Intake, db: Db, user: Staff):
    """Швидке приймання: клієнта шукаємо за телефоном, пристрій — наявний або новий, заявка створюється одним кроком."""
    if user.role == "master" and payload.master_id not in (None, user.id):
        fail(403, "Призначити іншого майстра може адміністратор.")
    validate_master(db, payload.master_id)
    claim_raw = None
    if payload.device_id:
        device = access_device(db, payload.device_id, user)
    else:
        client, claim_raw = find_or_create_client(db, payload.phone, payload.full_name)
        device = register_device(db, client, payload.device.model_dump())
        if payload.save_preset and device.specifications:
            exists = db.scalar(select(ModelPreset.id).where(
                ModelPreset.device_category == device.device_category, func.lower(ModelPreset.brand) == device.brand.lower(),
                func.lower(ModelPreset.model_name) == device.model.lower()))
            if not exists:
                add_preset(db, {"device_category": device.device_category, "brand": device.brand,
                                "model_name": device.model, "default_specs": device.specifications})
    active_warranty = warranty(db, device.id)
    if payload.is_warranty_case and not active_warranty:
        fail(422, "На пристрій немає чинної гарантії.")
    fields = payload.model_dump(include={"problem_description", "completeness", "cosmetic_notes", "priority",
                                         "master_id", "is_warranty_case", "delivery"})
    if user.role == "master" and fields["master_id"] is None:
        fields["master_id"] = user.id
    order = new_order(db, user, device, fields)
    db.commit()
    return dict(order_details(db, order, user), active_warranty=active_warranty, claim_token=claim_raw)

@router.patch("/passports/{device_id}/serial")
def set_serial(device_id: int, payload: SerialInput, db: Db, user: Staff):
    device = access_device(db, device_id, user, lock=True)
    other = db.scalar(select(Device.id).where(Device.serial_number == payload.serial_number, Device.id != device.id))
    if other:
        fail(409, "Цей серійний номер уже закріплено за іншим пристроєм.")
    change_identity(db, device, "serial_number", payload.serial_number, user.id, "Внесення серійного номера")
    db.commit()
    return {"id": device.id, "serial_number": device.serial_number}
