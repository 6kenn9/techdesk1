from fastapi import APIRouter, Query
from sqlalchemy import or_, select
from ..core.security import Current, Db, Staff, fail
from ..models.models import Device, Order, OrderPart, Service, StatusHistory, User, Work, now
from ..schemas.schemas import Approval, OrderCreate, OrderEdit, OrderPartInput, Quantity, Transition, WorkInput
from ..services.domain import (ACTIVE, access_device, access_order, add_part, ensure_draft, estimate_version, lock_part,
                               new_order, order_details, order_summary, refresh_totals, stock_move, transition, warranty)

router = APIRouter(prefix="/api/orders")

@router.get("")
def list_orders(db: Db, user: Current, q: str = Query("", max_length=160), status: str = "",
                category: str = "", master_id: int | None = None, warranty_only: bool = False):
    query = select(Order).join(Device, Order.device_id == Device.id).join(User, Order.client_id == User.id)
    if user.role == "client":
        query = query.where(Order.client_id == user.id)
    if q:
        query = query.where(or_(*(column.icontains(q, autoescape=True) for column in
                                 (Order.order_number, Device.serial_number, Device.model, User.full_name))))
    if status:
        query = query.where(Order.status == status)
    if category:
        query = query.where(Device.device_category == category)
    if master_id:
        query = query.where(Order.master_id == master_id)
    if warranty_only:
        query = query.where(Order.is_warranty_case.is_(True))
    return [order_summary(db, order) for order in db.scalars(query.order_by(Order.created_at.desc(), Order.id.desc()))]

def validate_master(db, master_id):
    if master_id is not None:
        master = db.get(User, master_id)
        if not master or master.role != "master" or not master.is_active:
            fail(422, "Оберіть активного майстра.")

@router.post("", status_code=201)
def create_order(payload: OrderCreate, db: Db, user: Current):
    if bool(payload.device_id) == bool(payload.new_device):
        fail(422, "Оберіть наявний пристрій або внесіть дані нового.")
    if payload.new_device:
        if user.role != "client":
            fail(422, "Спочатку зареєструйте паспорт клієнта.")
        device = Device(owner_id=user.id, **payload.new_device.model_dump())
        db.add(device)
        db.flush()
    else:
        device = access_device(db, payload.device_id, user)
    if user.role == "client" and (payload.master_id or payload.is_warranty_case):
        fail(403, "Гарантійний випадок і майстра визначає працівник центру.")
    if user.role == "master" and payload.master_id not in (None, user.id):
        fail(403, "Призначити іншого майстра може адміністратор.")
    validate_master(db, payload.master_id)
    active_warranty = warranty(db, device.id)
    order = new_order(db, user, device, payload.model_dump(exclude={"device_id", "new_device"}))
    db.commit()
    return dict(order_details(db, order, user), active_warranty=active_warranty)

@router.get("/{order_id}")
def detail(order_id: int, db: Db, user: Current):
    return order_details(db, access_order(db, order_id, user), user)

@router.put("/{order_id}")
def edit(order_id: int, payload: OrderEdit, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    fields = payload.model_dump(exclude_unset=True)
    if "master_id" in fields:
        if order.status not in ACTIVE:
            fail(409, "Заявку вже закрито.")
        if user.role != "admin" and (order.master_id is not None or fields["master_id"] != user.id):
            fail(403, "Ви можете взяти лише вільну заявку.")
        validate_master(db, fields["master_id"])
    if "diagnostics" in fields:
        ensure_draft(order)
    if "paid_amount" in fields:
        if order.status not in ("ready_for_pickup", "completed") or fields["paid_amount"] is None or fields["paid_amount"] > order.total_cost:
            fail(422, "Оплату можна облікувати після ремонту в межах суми замовлення.")
    if "warranty_days" in fields and order.status not in ACTIVE:
        fail(409, "Гарантійний строк завершеного ремонту зафіксовано.")
    for key, value in fields.items():
        if value is not None or key == "master_id":
            setattr(order, key, value)
    db.commit()
    return order_details(db, order, user)

@router.patch("/{order_id}/status")
def status(order_id: int, payload: Transition, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    transition(db, order, payload.status, user, payload.comment)
    db.commit()
    return order_details(db, order, user)

@router.post("/{order_id}/approve-cost")
def approval(order_id: int, payload: Approval, db: Db, user: Current):
    if user.role not in ("client", "admin"):
        fail(403, "Погодити вартість може клієнт або адміністратор.")
    order = access_order(db, order_id, user, write=True)
    if order.status != "waiting_approval" or order.client_approval_status != "pending":
        fail(409, "Заявка не очікує нового рішення.")
    if payload.expected_total != order.total_cost or payload.estimate_version != estimate_version(db, order):
        fail(409, "Кошторис змінився. Оновіть сторінку та перевірте суму.")
    if user.role == "admin" and not payload.comment:
        fail(422, "Зазначте, як отримано рішення клієнта.")
    order.client_approval_status = "approved" if payload.approved else "rejected"
    order.approved_at = now() if payload.approved else None
    order.approved_total = order.total_cost if payload.approved else None
    order.approval_comment = payload.comment
    if payload.approved and user.role == "client":
        transition(db, order, "in_repair", user, "Клієнт погодив кошторис у кабінеті")
    db.commit()
    return order_details(db, order, user)

def work_values(db, payload):
    service = db.get(Service, payload.service_id) if payload.service_id else None
    if payload.service_id and not service:
        fail(404, "Послугу не знайдено.")
    name = payload.work_name or (service.name if service else None)
    price = payload.price if payload.price is not None else (service.default_price if service else None)
    if not name or price is None:
        fail(422, "Вкажіть назву та ціну роботи.")
    return dict(service_id=payload.service_id, work_name=name, price=price,
                updates_passport_spec=payload.updates_passport_spec)

def saved(db, order, user):
    refresh_totals(db, order)
    db.commit()
    return order_details(db, order, user)

@router.post("/{order_id}/works", status_code=201)
def add_work(order_id: int, payload: WorkInput, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_draft(order)
    db.add(Work(order_id=order.id, master_id=order.master_id, **work_values(db, payload)))
    return saved(db, order, user)

def line(db, model, order_id, line_id):
    item = db.get(model, line_id)
    if not item or item.order_id != order_id:
        fail(404, "Позицію не знайдено.")
    return item

@router.patch("/{order_id}/works/{line_id}")
def edit_work(order_id: int, line_id: int, payload: WorkInput, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_draft(order)
    item = line(db, Work, order_id, line_id)
    for key, value in work_values(db, payload).items():
        setattr(item, key, value)
    return saved(db, order, user)

@router.delete("/{order_id}/works/{line_id}")
def delete_work(order_id: int, line_id: int, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_draft(order)
    db.delete(line(db, Work, order_id, line_id))
    return saved(db, order, user)

@router.post("/{order_id}/parts", status_code=201)
def add_order_part(order_id: int, payload: OrderPartInput, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_draft(order)
    part = lock_part(db, payload.part_id)
    if part.compatible_device_category and part.compatible_device_category != db.get(Device, order.device_id).device_category:
        fail(422, "Запчастина не підходить до категорії пристрою.")
    add_part(db, order, part, payload.quantity, user.id)
    return saved(db, order, user)

@router.patch("/{order_id}/parts/{line_id}")
def edit_order_part(order_id: int, line_id: int, payload: Quantity, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_draft(order)
    item = line(db, OrderPart, order_id, line_id)
    difference = item.quantity - payload.quantity
    if difference:
        stock_move(db, lock_part(db, item.part_id), difference, user.id, "Зміна кількості в заявці", order.id)
        item.quantity = payload.quantity
        item.total_sale_price = item.unit_sale_price * item.quantity
    return saved(db, order, user)

@router.delete("/{order_id}/parts/{line_id}")
def delete_order_part(order_id: int, line_id: int, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_draft(order)
    item = line(db, OrderPart, order_id, line_id)
    stock_move(db, lock_part(db, item.part_id), item.quantity, user.id, "Повернення з заявки", order.id)
    db.delete(item)
    return saved(db, order, user)
