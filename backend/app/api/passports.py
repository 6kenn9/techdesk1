from fastapi import APIRouter, Query
from sqlalchemy import or_, select
from ..core.security import Admin, Current, Db, Staff, fail
from ..models.models import Device, ModelPreset, User
from ..schemas.schemas import Defect, DeviceCreate, Hardware, PresetCreate, Upgrade
from ..services.domain import access_device, access_order, add_preset, change_spec, passport, row

router = APIRouter(prefix="/api/passports")

@router.get("")
def list_passports(db: Db, user: Current, q: str = Query("", max_length=160), category: str = ""):
    query = select(Device).join(User, Device.owner_id == User.id).order_by(Device.id.desc())
    if user.role == "client":
        query = query.where(Device.owner_id == user.id)
    if q:
        query = query.where(or_(*(col.icontains(q, autoescape=True) for col in (
            Device.serial_number, Device.brand, Device.model, User.full_name, User.phone))))
    if category:
        query = query.where(Device.device_category == category)
    return [passport(db, device, user) for device in db.scalars(query)]

@router.get("/presets")
def presets(db: Db, user: Current):
    return [row(preset) for preset in db.scalars(select(ModelPreset).order_by(ModelPreset.brand, ModelPreset.model_name))]

@router.post("/presets", status_code=201)
def create_preset(payload: PresetCreate, db: Db, user: Admin):
    preset = add_preset(db, payload.model_dump())
    db.commit()
    return row(preset)

@router.put("/presets/{preset_id}")
def update_preset(preset_id: int, payload: PresetCreate, db: Db, user: Admin):
    preset = db.get(ModelPreset, preset_id)
    if not preset:
        fail(404, "Модель не знайдено.")
    for key, value in payload.model_dump().items():
        setattr(preset, key, value)
    db.commit()
    return row(preset)

@router.get("/lookup-sn/{serial_number:path}")
def lookup(serial_number: str, db: Db, user: Staff):
    device = db.scalar(select(Device).where(Device.serial_number == serial_number.strip().upper()))
    return passport(db, device, user, True) if device else None

@router.post("", status_code=201)
def create_passport(payload: DeviceCreate, db: Db, user: Staff):
    owner = db.get(User, payload.owner_id)
    if not owner or owner.role != "client" or not owner.is_active:
        fail(422, "Оберіть активного клієнта.")
    device = Device(**payload.model_dump(exclude={"save_preset"}))
    db.add(device)
    if payload.save_preset:
        add_preset(db, {"device_category": device.device_category, "brand": device.brand,
                       "model_name": device.model, "default_specs": device.specifications})
    db.commit()
    return passport(db, device, user, True)

@router.get("/{device_id}")
def get_passport(device_id: int, db: Db, user: Current):
    return passport(db, access_device(db, device_id, user), user, True)

@router.put("/{device_id}")
def update_passport(device_id: int, payload: Hardware, db: Db, user: Staff):
    device = access_device(db, device_id, user, lock=True)
    for key in set(device.specifications) | set(payload.specifications):
        change_spec(db, device, key, payload.specifications.get(key, ""), user.id, "Редагування паспорта")
    for key, value in payload.model_dump(exclude={"specifications"}).items():
        setattr(device, key, value)
    db.commit()
    return passport(db, device, user, True)

@router.post("/{device_id}/upgrade-spec")
def upgrade(device_id: int, payload: Upgrade, db: Db, user: Staff):
    if payload.order_id:
        order = access_order(db, payload.order_id, user, write=True)
        if order.device_id != device_id or order.status not in ("in_repair", "ready_for_pickup"):
            fail(409, "Оновлення доступне для пристрою в ремонті або після перевірки.")
    device = access_device(db, device_id, user, lock=True)
    change_spec(db, device, payload.field_name, payload.new_value, user.id,
                payload.change_reason or "Модернізація пристрою", payload.order_id)
    db.commit()
    return passport(db, device, user, True)

@router.post("/{device_id}/defects")
def add_defect(device_id: int, payload: Defect, db: Db, user: Staff):
    device = access_device(db, device_id, user, lock=True)
    device.known_defects_history = [*device.known_defects_history, payload.description]
    db.commit()
    return passport(db, device, user, True)
