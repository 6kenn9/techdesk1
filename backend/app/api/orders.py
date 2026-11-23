from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select
from ..core.security import Current, Db, Staff, fail
import csv
import io
import re
from datetime import date as day_type
from decimal import Decimal
from fastapi import Response
from ..models.models import Device, Order, OrderPart, Payment, Service, StatusHistory, User, Work, now
from ..schemas.schemas import Approval, ClientCancel, Delivery, RatingInput, Shipment, OrderCreate, OrderEdit, OrderPartInput, PaymentInput, Quantity, Transition, WorkInput
from ..services.domain import (ACTIVE, amount_due, apply_delivery, stage_started, access_device, access_order, add_part, decide_estimate, ensure_draft, ensure_estimate_editable, estimate_version,
                               CLOSED, LABELS, local_date, lock_part, new_order, order_details, order_summary, preload, recheck_approval, refresh_totals,
                               repair_started, stock_move, transition, warranty)
from ..services.notifications import emit

router = APIRouter(prefix="/api/orders")

def filtered_orders(db, user, q, status, category, master_id, warranty_only):
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
    return list(db.scalars(query.order_by(Order.created_at.desc(), Order.id.desc())))

@router.get("")
def list_orders(db: Db, user: Current, q: str = Query("", max_length=160), status: str = "",
                category: str = "", master_id: int | None = None, warranty_only: bool = False):
    orders = filtered_orders(db, user, q, status, category, master_id, warranty_only)
    loaded = preload(db, orders)
    since = stage_started(db, [order.id for order in orders])
    result = [order_summary(db, order, since.get(order.id, order.created_at)) for order in orders]
    del loaded
    return result

def money_text(value):
    return f"{Decimal(value or 0):.2f}".replace(".", ",")

SAFE_SIGNED = re.compile(r"[+-][\d\s().,-]*")

def csv_cell(value):
    if isinstance(value, str) and value[:1] in ("=", "@", "\t", "\r", "+", "-") and not SAFE_SIGNED.fullmatch(value):
        return "'" + value
    return value

def csv_response(rows, filename):
    buffer = io.StringIO()
    csv.writer(buffer, delimiter=";", lineterminator="\r\n").writerows([csv_cell(value) for value in row] for row in rows)
    return Response(("\ufeff" + buffer.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})

EXPORT_HEADER = ["Номер", "Створено", "Клієнт", "Телефон", "Пристрій", "Категорія", "Серійний номер", "Етап", "Майстер",
                 "Пріоритет", "Гарантійний", "Сума, грн", "Оплачено, грн", "Завершено", "Отримання", "ТТН", "Оцінка"]

def export_rows(db, orders):
    devices, people = preload(db, orders)
    rows = []
    for order in orders:
        device, client = devices[order.device_id], people[order.client_id]
        master = people.get(order.master_id)
        rows.append([order.order_number, local_date(order.created_at), client.full_name, client.phone,
                     f"{device.brand} {device.model}", device.device_category, device.serial_number or "", LABELS[order.status],
                     master.full_name if master else "", "терміновий" if order.priority == "urgent" else "звичайний",
                     "так" if order.is_warranty_case else "ні", Decimal(order.total_cost or 0), Decimal(order.paid_amount or 0),
                     local_date(order.completed_at) if order.completed_at else None,
                     f"Нова Пошта: {order.delivery_city}, {order.delivery_branch}" if order.delivery_method == "nova_poshta" else "самовивіз",
                     order.delivery_ttn or "", order.rating])
    return rows

def export_name(extension):
    return f"techdesk-orders-{local_date(now()).isoformat()}.{extension}"

@router.get("/export.csv")
def export_orders(db: Db, user: Staff, q: str = Query("", max_length=160), status: str = "",
                  category: str = "", master_id: int | None = None, warranty_only: bool = False):
    orders = filtered_orders(db, user, q, status, category, master_id, warranty_only)
    def text(value):
        if isinstance(value, Decimal):
            return money_text(value)
        if isinstance(value, day_type):
            return value.strftime("%d.%m.%Y")
        return "" if value is None else value
    rows = [EXPORT_HEADER] + [[text(value) for value in row] for row in export_rows(db, orders)]
    return csv_response(rows, export_name("csv"))

@router.get("/export.xlsx")
def export_orders_xlsx(db: Db, user: Staff, q: str = Query("", max_length=160), status: str = "",
                       category: str = "", master_id: int | None = None, warranty_only: bool = False):
    from ..services.excel import table_sheet, xlsx_response
    rows = export_rows(db, filtered_orders(db, user, q, status, category, master_id, warranty_only))
    return xlsx_response(lambda wb: table_sheet(wb, "Заявки", EXPORT_HEADER, rows), export_name("xlsx"))

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
    if (payload.is_warranty_case or payload.warranty_claim) and not active_warranty:
        fail(422, "На пристрій немає чинної гарантії.")
    fields = payload.model_dump(exclude={"device_id", "new_device"})
    if user.role == "client":
        fields["priority"] = "normal"
    else:
        fields["warranty_claim"] = False
    order = new_order(db, user, device, fields)
    db.commit()
    return dict(order_details(db, order, user), active_warranty=active_warranty)

@router.post("/{order_id}/receive")
def receive_device(order_id: int, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True, take=True)
    if order.device_received_at:
        fail(409, "Пристрій уже отримано.")
    if order.status != "registered":
        fail(409, "Позначити отримання можна лише для щойно оформленої заявки.")
    order.device_received_at = now()
    db.commit()
    return order_details(db, order, user)

@router.get("/{order_id}")
def detail(order_id: int, db: Db, user: Current):
    return order_details(db, access_order(db, order_id, user), user)

@router.put("/{order_id}")
def edit(order_id: int, payload: OrderEdit, db: Db, user: Staff):
    fields = payload.model_dump(exclude_unset=True)
    order = access_order(db, order_id, user, write=True, take=fields.get("master_id") == user.id and set(fields) == {"master_id"})
    if "master_id" in fields:
        if order.status not in ACTIVE and not (order.status == "cancelled" and order.device_received_at):
            fail(409, "Заявку вже закрито.")
        if user.role != "admin" and (order.master_id is not None or fields["master_id"] != user.id):
            fail(403, "Ви можете взяти лише вільну заявку.")
        if fields["master_id"] is None and order.status != "registered":
            fail(409, "Після початку діагностики заявку можна лише передати іншому майстру.")
        validate_master(db, fields["master_id"])
    if "diagnostics" in fields:
        ensure_estimate_editable(order)
    if "paid_amount" in fields:
        if not payable(order) or fields["paid_amount"] is None or fields["paid_amount"] > amount_due(order):
            fail(422, "Оплату приймають, коли пристрій готовий до видачі, у межах суми замовлення.")
        if fields["paid_amount"] < order.paid_amount:
            fail(422, "Облікову оплату не можна зменшити: кожна оплата зберігається окремим записом.")
        if fields["paid_amount"] > order.paid_amount:
            db.add(Payment(order_id=order.id, amount=fields["paid_amount"] - order.paid_amount, method="cash", created_by_id=user.id))
    if "warranty_days" in fields and order.status not in ACTIVE:
        fail(409, "Гарантійний строк завершеного ремонту зафіксовано.")
    if fields.get("is_warranty_case") is not None:
        ensure_draft(order)
        if fields["is_warranty_case"] and not warranty(db, order.device_id):
            fail(422, "На пристрій немає чинної гарантії.")
    if "master_id" in fields and fields["master_id"] and fields["master_id"] != order.master_id:
        emit(db, "assigned", order.id)
    for key, value in fields.items():
        if value is not None or key == "master_id":
            setattr(order, key, value)
    if fields.get("is_warranty_case") is not None:
        refresh_totals(db, order)
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
    decide_estimate(db, order, user, payload.approved, payload.comment)
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

def sync_warranty(db, order):
    days = db.scalar(select(func.max(Service.warranty_days)).join(Work, Work.service_id == Service.id)
                     .where(Work.order_id == order.id))
    if days is not None:
        order.warranty_days = days

def saved(db, order, user, works_changed=False):
    refresh_totals(db, order)
    if works_changed:
        sync_warranty(db, order)
    recheck_approval(db, order)
    db.commit()
    return order_details(db, order, user)

@router.post("/{order_id}/works", status_code=201)
def add_work(order_id: int, payload: WorkInput, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_estimate_editable(order)
    db.add(Work(order_id=order.id, master_id=order.master_id, **work_values(db, payload)))
    return saved(db, order, user, works_changed=True)

def line(db, model, order_id, line_id):
    item = db.get(model, line_id)
    if not item or item.order_id != order_id:
        fail(404, "Позицію не знайдено.")
    return item

@router.patch("/{order_id}/works/{line_id}")
def edit_work(order_id: int, line_id: int, payload: WorkInput, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_estimate_editable(order)
    item = line(db, Work, order_id, line_id)
    for key, value in work_values(db, payload).items():
        setattr(item, key, value)
    return saved(db, order, user, works_changed=True)

@router.delete("/{order_id}/works/{line_id}")
def delete_work(order_id: int, line_id: int, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_estimate_editable(order)
    db.delete(line(db, Work, order_id, line_id))
    return saved(db, order, user, works_changed=True)

@router.post("/{order_id}/parts", status_code=201)
def add_order_part(order_id: int, payload: OrderPartInput, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_estimate_editable(order)
    part = lock_part(db, payload.part_id)
    if part.compatible_device_category and part.compatible_device_category != db.get(Device, order.device_id).device_category:
        fail(422, "Запчастина не підходить до категорії пристрою.")
    add_part(db, order, part, payload.quantity, user.id)
    return saved(db, order, user)

@router.patch("/{order_id}/parts/{line_id}")
def edit_order_part(order_id: int, line_id: int, payload: Quantity, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    ensure_estimate_editable(order)
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
    ensure_estimate_editable(order)
    item = line(db, OrderPart, order_id, line_id)
    stock_move(db, lock_part(db, item.part_id), item.quantity, user.id, "Повернення з заявки", order.id)
    db.delete(item)
    return saved(db, order, user)

def payable(order):
    return order.status == "ready_for_pickup" or (order.status == "cancelled" and amount_due(order) > 0)

PAYMENT_METHODS = {"cash": "готівка", "card": "картка", "transfer": "переказ"}

@router.post("/{order_id}/payments", status_code=201)
def add_payment(order_id: int, payload: PaymentInput, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    if not payable(order):
        fail(409, "Оплату приймають, коли пристрій готовий до видачі, або за виконані роботи скасованого ремонту.")
    due = amount_due(order) - order.paid_amount
    if payload.amount > due:
        fail(422, f"Сума перевищує залишок до сплати ({due} грн).")
    db.add(Payment(order_id=order.id, amount=payload.amount, method=payload.method, note=payload.note, created_by_id=user.id))
    order.paid_amount += payload.amount
    db.commit()
    return order_details(db, order, user)

@router.post("/{order_id}/cancel")
def client_cancel(order_id: int, payload: ClientCancel, db: Db, user: Current):
    if user.role != "client":
        fail(403, "Працівники змінюють етап заявки в блоці керування.")
    order = access_order(db, order_id, user, write=True)
    rejected = order.status == "waiting_approval" and order.client_approval_status == "rejected" and not repair_started(order)
    if order.status != "registered" and not rejected:
        fail(409, "Заявку вже взято в роботу. Щоб скасувати її, зверніться до сервісного центру.")
    comment = payload.comment.strip()
    transition(db, order, "cancelled", user, "Скасовано клієнтом" + (f": {comment}" if comment else ""))
    from ..services.inbox import describe, notify_staff
    notify_staff(db, order, "cancelled", f"Клієнт скасував заявку: {describe(db, order)}" + (f". Причина: {comment}" if comment else ""), user.id)
    db.commit()
    return order_details(db, order, user)

@router.put("/{order_id}/delivery")
def change_delivery(order_id: int, payload: Delivery, db: Db, user: Current):
    order = access_order(db, order_id, user, write=True)
    if order.status in CLOSED or order.delivery_ttn or not order.device_received_at and order.status == "cancelled":
        fail(409, "Спосіб отримання вже не можна змінити.")
    for key, value in apply_delivery(payload.model_dump()).items():
        setattr(order, key, value)
    if user.role == "client":
        from ..services.inbox import describe, notify_staff
        where = f"Нова Пошта, {order.delivery_city}, {order.delivery_branch}" + (f", отримувач {order.delivery_recipient_name}" if order.delivery_recipient_name else "") if order.delivery_method == "nova_poshta" else "самовивіз"
        notify_staff(db, order, "delivery", f"Клієнт змінив спосіб отримання ({where}): {describe(db, order)}", user.id)
    db.commit()
    return order_details(db, order, user)

@router.post("/{order_id}/shipment")
def ship(order_id: int, payload: Shipment, db: Db, user: Staff):
    order = access_order(db, order_id, user, write=True)
    if order.delivery_method != "nova_poshta":
        fail(409, "Клієнт обрав самовивіз.")
    if order.status not in ("ready_for_pickup", "cancelled"):
        fail(409, "Відправити можна відремонтований пристрій або повернути пристрій після скасування.")
    if order.status == "cancelled" and not order.device_received_at:
        fail(409, "Пристрій не надходив до центру, тому відправляти нічого.")
    if order.paid_amount < amount_due(order):
        fail(409, "Перед відправкою облікуйте повну оплату замовлення.")
    if payload.ttn == order.delivery_ttn:
        return order_details(db, order, user)
    order.delivery_ttn = payload.ttn
    emit(db, "shipped", order.id)
    db.commit()
    return order_details(db, order, user)

@router.post("/{order_id}/rating")
def rate(order_id: int, payload: RatingInput, db: Db, user: Current):
    if user.role != "client":
        fail(403, "Оцінку залишає клієнт.")
    order = access_order(db, order_id, user, write=True)
    if order.status != "completed":
        fail(409, "Оцінити можна завершений ремонт.")
    if order.rating is not None:
        fail(409, "Ви вже оцінили цей ремонт.")
    order.rating, order.rating_comment, order.rated_at = payload.rating, payload.comment.strip(), now()
    from ..services.inbox import describe, notify_staff
    text = f"Оцінка {'★' * payload.rating}{'☆' * (5 - payload.rating)}: {describe(db, order)}"
    notify_staff(db, order, "rating", text + (f". «{order.rating_comment}»" if order.rating_comment else ""), user.id)
    db.commit()
    return order_details(db, order, user)
