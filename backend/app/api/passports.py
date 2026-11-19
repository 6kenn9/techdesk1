from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from sqlalchemy import func
from sqlalchemy import or_, select
from ..core.security import Admin, Current, Db, Staff, fail
from ..models.models import Device, DevicePhoto, ModelPreset, Order, SpecHistory, User
from ..schemas.schemas import Defect, DeviceCreate, Hardware, OwnerTransfer, PresetCreate, Upgrade
from ..services.domain import IDENTITY_FIELDS, access_device, still_open, access_order, add_preset, change_identity, change_spec, passport, row, warranties

def visible_to(query, user):
    """Клієнт бачить фото пристрою без заявки та фото власних заявок, але не заявок попереднього власника."""
    if user.role != "client":
        return query
    return query.where(or_(DevicePhoto.order_id.is_(None),
                           DevicePhoto.order_id.in_(select(Order.id).where(Order.client_id == user.id))))

from ..services.photos import MAX_PER_DEVICE, MAX_UPLOAD_BYTES, normalize

router = APIRouter(prefix="/api/passports")
photos = APIRouter(prefix="/api/photos")

@router.get("")
def list_passports(db: Db, user: Current, q: str = Query("", max_length=160), category: str = ""):
    query = select(Device, User.full_name).join(User, Device.owner_id == User.id).order_by(Device.id.desc())
    if user.role == "client":
        query = query.where(Device.owner_id == user.id)
    if q:
        query = query.where(or_(*(col.icontains(q, autoescape=True) for col in (
            Device.serial_number, Device.brand, Device.model, User.full_name, User.phone))))
    if category:
        query = query.where(Device.device_category == category)
    found = db.execute(query).all()
    active = warranties(db, [device.id for device, _ in found])
    return [passport(db, device, user, warranty_info=active.get(device.id), owner_name=owner) for device, owner in found]

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
        if key in IDENTITY_FIELDS:
            change_identity(db, device, key, value, user.id, "Редагування паспорта")
        else:
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

@router.post("/{device_id}/transfer")
def transfer(device_id: int, payload: OwnerTransfer, db: Db, user: Admin):
    """Пристрій продали чи подарували: паспорт з усією історією переходить до іншого клієнта.
    Попередні заявки лишаються за старим власником, нові оформлюються на нового."""
    device = access_device(db, device_id, user, lock=True)
    owner = db.get(User, payload.owner_id)
    if not owner or owner.role != "client" or not owner.is_active:
        fail(422, "Оберіть активного клієнта.")
    if owner.id == device.owner_id:
        fail(409, "Пристрій уже належить цьому клієнту.")
    if db.scalar(select(Order.order_number).where(Order.device_id == device.id, still_open()).limit(1)):
        fail(409, "Пристрій ще в сервісі: спершу завершіть заявку або позначте пристрій повернутим клієнту.")
    previous = db.get(User, device.owner_id)
    db.add(SpecHistory(device_id=device.id, changed_by_id=user.id, field_name="owner", old_value=previous.full_name,
                       new_value=owner.full_name, change_reason=payload.reason or "Зміна власника пристрою"))
    device.owner_id = owner.id
    db.commit()
    return passport(db, device, user, True)

@router.post("/{device_id}/defects")
def add_defect(device_id: int, payload: Defect, db: Db, user: Staff):
    device = access_device(db, device_id, user, lock=True)
    device.known_defects_history = [*device.known_defects_history, payload.description]
    db.commit()
    return passport(db, device, user, True)

def photo_info(db, photo):
    order = db.get(Order, photo.order_id) if photo.order_id else None
    return {"id": photo.id, "device_id": photo.device_id, "order_id": photo.order_id,
            "order_number": order.order_number if order else None, "caption": photo.caption,
            "width": photo.width, "height": photo.height, "size_bytes": photo.size_bytes,
            "created_at": photo.created_at, "uploaded_by_id": photo.uploaded_by_id,
            "uploaded_by": db.get(User, photo.uploaded_by_id).full_name}

@router.get("/{device_id}/photos")
def list_photos(device_id: int, db: Db, user: Current, order_id: int | None = None):
    access_device(db, device_id, user)
    query = visible_to(select(DevicePhoto).where(DevicePhoto.device_id == device_id), user)
    if order_id:
        query = query.where(DevicePhoto.order_id == order_id)
    return [photo_info(db, photo) for photo in db.scalars(query.order_by(DevicePhoto.created_at.desc(), DevicePhoto.id.desc()))]

@router.post("/{device_id}/photos", status_code=201)
def upload_photo(device_id: int, db: Db, user: Staff, file: UploadFile = File(...),
                 caption: str = Form("", max_length=200), order_id: int | None = Form(None)):
    access_device(db, device_id, user)
    if order_id:
        order = access_order(db, order_id, user, write=True)
        if order.device_id != device_id:
            fail(422, "Заявка стосується іншого пристрою.")
    if db.scalar(select(func.count(DevicePhoto.id)).where(DevicePhoto.device_id == device_id)) >= MAX_PER_DEVICE:
        fail(409, f"Для пристрою можна зберегти до {MAX_PER_DEVICE} фото.")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        fail(413, "Фото завелике: максимум 10 МБ.")
    content, width, height = normalize(data)
    photo = DevicePhoto(device_id=device_id, order_id=order_id, uploaded_by_id=user.id, caption=caption.strip(),
                        content=content, width=width, height=height, size_bytes=len(content))
    db.add(photo)
    db.commit()
    return photo_info(db, photo)

@photos.get("/{photo_id}")
def photo_file(photo_id: int, db: Db, user: Current):
    photo = db.scalar(visible_to(select(DevicePhoto).where(DevicePhoto.id == photo_id), user))
    if not photo:
        fail(404, "Фото не знайдено.")
    access_device(db, photo.device_id, user)
    return Response(photo.content, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})

@photos.delete("/{photo_id}")
def delete_photo(photo_id: int, db: Db, user: Staff):
    photo = db.get(DevicePhoto, photo_id)
    if not photo:
        fail(404, "Фото не знайдено.")
    if user.role != "admin" and photo.uploaded_by_id != user.id:
        fail(403, "Видалити фото може автор або адміністратор.")
    db.delete(photo)
    db.commit()
    return {"deleted": photo_id}
