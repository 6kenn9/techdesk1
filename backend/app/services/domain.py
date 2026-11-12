from datetime import timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from zoneinfo import ZoneInfo
from sqlalchemy import Integer, cast, func, select, text
from ..core.security import fail
from ..models.models import Device, ModelPreset, Movement, Order, OrderPart, Part, Payment, SpecHistory, StatusHistory, User, Work, now

STAGES = ("registered", "diagnostics", "waiting_approval", "in_repair", "ready_for_pickup", "completed")
# «Скасована» — ремонт припинено, але пристрій ще в сервісі; «Повернуто клієнту» — пристрій віддано без звичайної видачі.
LABELS = dict(zip(STAGES + ("cancelled", "returned"), (
    "Зареєстрована", "На діагностиці", "Очікує погодження вартості", "У ремонті",
    "Готова до видачі", "Завершена", "Скасована", "Повернуто клієнту",
)))
SPEC_LABELS = {
    "cpu": "Процесор", "ram": "Оперативна пам’ять", "storage": "Накопичувач",
    "gpu": "Відеокарта", "display": "Дисплей", "os": "Операційна система",
    "battery_health": "Стан акумулятора", "motherboard": "Материнська плата", "psu": "Блок живлення",
    "cooling": "Корпус і охолодження", "color": "Колір", "case_size": "Розмір корпусу",
    "case_material": "Матеріал корпусу", "seal": "Стан ущільнення", "revision": "Ревізія плати",
    "power": "Потужність", "ports": "Роз’єми", "condition": "Стан компонента",
}
ACTIVE = STAGES[:5]
DRAFT = STAGES[:2]
CLOSED = ("completed", "returned")  # пристрій уже в клієнта: заявку більше не змінюють
# Допустимі переходи між етапами заявки (діаграма станів у записці).
ALLOWED = {
    "registered": {"diagnostics", "cancelled"},
    "diagnostics": {"waiting_approval", "cancelled"},
    "waiting_approval": {"in_repair", "diagnostics", "cancelled"},
    # під час ремонту знайшли ще несправність — доплату знову погоджує клієнт
    "in_repair": {"ready_for_pickup", "waiting_approval", "cancelled"},
    # клієнт не забрав пристрій або відмовився платити — повертаємо без звичайної видачі
    "ready_for_pickup": {"completed", "returned"},
    # скасований пристрій лишається в сервісі, доки його не віддадуть клієнту
    "cancelled": {"returned"},
}

def repair_started(order):
    """Клієнт хоч раз погодив кошторис: роботи почалися, деталі вважаються встановленими."""
    return order.approved_total is not None

def order_total(works_total, parts_total, warranty_case=False):
    """Сума до сплати клієнтом: гарантійний ремонт виконується безкоштовно."""
    return Decimal(0) if warranty_case else works_total + parts_total

def local_date(value):
    return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(ZoneInfo("Europe/Kyiv")).date()

def row(record, *exclude):
    return {c.key: getattr(record, c.key) for c in record.__table__.columns if c.key not in exclude}

def public_user(user):
    return dict(row(user, "password_hash", "telegram_chat_id", "telegram_link_code", "telegram_link_expires_at",
                    "claim_token_hash", "claim_expires_at", "token_version"),
                telegram_linked=user.telegram_chat_id is not None, is_guest=user.email is None)

def access_device(db, device_id, user, lock=False):
    query = select(Device).where(Device.id == device_id)
    if lock:
        query = query.with_for_update()
    device = db.scalar(query)
    if not device or (user.role == "client" and device.owner_id != user.id):
        fail(404, "Паспорт пристрою не знайдено.")
    return device

def access_order(db, order_id, user, write=False):
    query = select(Order).where(Order.id == order_id)
    if write:
        query = query.with_for_update()
    order = db.scalar(query)
    if not order or (user.role == "client" and order.client_id != user.id):
        fail(404, "Заявку не знайдено.")
    if write and user.role == "master" and order.master_id not in (None, user.id):
        fail(403, "Заявка закріплена за іншим майстром.")
    return order

def preload(db, orders):
    """Завантажує пристрої й людей для списку заявок кількома запитами замість окремого запиту на кожен рядок.
    Повертає ({id: Device}, {id: User}); поки словники живі, db.get бере ці записи з сесії без звернення до бази."""
    device_ids = {order.device_id for order in orders}
    user_ids = {order.client_id for order in orders} | {order.master_id for order in orders if order.master_id}
    devices = {item.id: item for item in db.scalars(select(Device).where(Device.id.in_(device_ids)))} if device_ids else {}
    people = {item.id: item for item in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    return devices, people

def warranties(db, device_ids):
    """Чинна гарантія для кожного з пристроїв: {device_id: {...}}; пристроїв без гарантії в словнику немає."""
    device_ids = list(device_ids)
    if not device_ids:
        return {}
    today = local_date(now())
    found = {}
    for order in db.scalars(select(Order).where(
            Order.device_id.in_(device_ids), Order.status == "completed", Order.warranty_expires_at.is_not(None),
    ).order_by(Order.warranty_expires_at.desc())):
        if order.device_id not in found and local_date(order.warranty_expires_at) >= today:
            found[order.device_id] = order
    if not found:
        return {}
    order_ids = [order.id for order in found.values()]
    names = {}
    for order_id, name in db.execute(select(Work.order_id, Work.work_name).where(Work.order_id.in_(order_ids)).order_by(Work.id)):
        names.setdefault(order_id, []).append(name)
    master_ids = {order.master_id for order in found.values() if order.master_id}
    masters = dict(db.execute(select(User.id, User.full_name).where(User.id.in_(master_ids))).all()) if master_ids else {}
    return {device_id: {"order_number": order.order_number, "expires_at": local_date(order.warranty_expires_at),
                        "works": names.get(order.id, []), "master": masters.get(order.master_id)}
            for device_id, order in found.items()}

def warranty(db, device_id):
    return warranties(db, [device_id]).get(device_id)

def add_preset(db, fields):
    existing = db.scalar(select(ModelPreset).filter_by(
        device_category=fields["device_category"], brand=fields["brand"], model_name=fields["model_name"]))
    if existing:
        fail(409, "Така модель уже є в довіднику.")
    preset = ModelPreset(**fields)
    db.add(preset)
    return preset

_MISSING = object()

def passport(db, device, user, details=False, warranty_info=_MISSING, owner_name=None):
    """warranty_info і owner_name передає список паспортів, щоб не робити окремих запитів на кожен пристрій."""
    data = row(device)
    data["warranty"] = warranty(db, device.id) if warranty_info is _MISSING else warranty_info
    data["owner_name"] = owner_name if owner_name is not None else db.get(User, device.owner_id).full_name
    if details:
        orders = select(Order).where(Order.device_id == device.id).order_by(Order.created_at.desc(), Order.id.desc())
        if user.role == "client":
            orders = orders.where(Order.client_id == user.id)
        data["orders"] = [order_summary(db, order) for order in db.scalars(orders)]
        data["spec_history"] = []
        for change in db.scalars(select(SpecHistory).where(SpecHistory.device_id == device.id)
                                 .order_by(SpecHistory.changed_at.desc(), SpecHistory.id.desc())):
            entry = dict(row(change), technician=db.get(User, change.changed_by_id).full_name,
                         order_number=db.get(Order, change.order_id).order_number if change.order_id else None)
            if change.field_name == "owner" and user.role == "client":
                # новий власник бачить сам факт передачі, але не ім'я попереднього
                entry.update(old_value="попередній власник", new_value="новий власник")
            data["spec_history"].append(entry)
    return data

def change_spec(db, device, field, value, user_id, reason, order_id=None):
    old = device.specifications.get(field, "")
    if old == value:
        return
    new_specs = dict(device.specifications)
    if value:
        new_specs[field] = value
    else:
        new_specs.pop(field, None)
    device.specifications = new_specs
    db.add(SpecHistory(device_id=device.id, order_id=order_id, changed_by_id=user_id, field_name=field,
                       old_value=old, new_value=value, change_reason=reason))

def stage_started(db, order_ids=None):
    """Час останньої зміни етапу для кожної заявки: {order_id: datetime}."""
    query = select(StatusHistory.order_id, func.max(StatusHistory.changed_at)).group_by(StatusHistory.order_id)
    if order_ids is not None:
        query = query.where(StatusHistory.order_id.in_(order_ids))
    return dict(db.execute(query).all())

def order_summary(db, order, stage_since=None):
    device = db.get(Device, order.device_id)
    client = db.get(User, order.client_id)
    master = db.get(User, order.master_id) if order.master_id else None
    if stage_since is None:
        stage_since = stage_started(db, [order.id]).get(order.id, order.created_at)
    return dict(row(order, "internal_notes", "approval_comment"), device=f"{device.brand} {device.model}",
                serial_number=device.serial_number, category=device.device_category, client=client.full_name,
                master=master.full_name if master else None, stage_since=stage_since)

def works(db, order):
    return list(db.scalars(select(Work).where(Work.order_id == order.id).order_by(Work.id)))

def parts(db, order):
    return list(db.scalars(select(OrderPart).where(OrderPart.order_id == order.id).order_by(OrderPart.id)))

def order_details(db, order, user):
    data = order_summary(db, order)
    data["works"] = [row(item) for item in works(db, order)]
    data["parts"] = [row(item, "unit_cost_price") for item in parts(db, order)]
    data["history"] = [
        row(change, "comment", "changed_by_id") if user.role == "client" else row(change)
        for change in db.scalars(select(StatusHistory).where(StatusHistory.order_id == order.id)
                                 .order_by(StatusHistory.changed_at, StatusHistory.id))
    ]
    data["estimate_version"] = estimate_version(db, order)
    data["payments"] = [row(item, "created_by_id") for item in db.scalars(
        select(Payment).where(Payment.order_id == order.id).order_by(Payment.created_at, Payment.id))]
    if user.role != "client":
        data["internal_notes"] = order.internal_notes
        data["approval_comment"] = order.approval_comment
    return data

def estimate_version(db, order):
    # Лише те, що бачить клієнт у кошторисі: нотатки працівників чи зміна доставки не мають скасовувати погодження.
    signature = (
        order.diagnostics, bool(order.is_warranty_case), str(order.total_cost),
        [(item.id, item.work_name, str(item.price)) for item in works(db, order)],
        [(item.id, item.quantity, str(item.unit_sale_price)) for item in parts(db, order)],
    )
    return sha256(repr(signature).encode()).hexdigest()

def refresh_totals(db, order):
    db.flush()
    order.works_total = sum(item.price for item in works(db, order))
    order.parts_total = sum(item.total_sale_price for item in parts(db, order))
    order.total_cost = order_total(order.works_total, order.parts_total, order.is_warranty_case)
    order.updated_at = now()

def ensure_draft(order):
    if order.status not in DRAFT:
        fail(409, "Змінювати кошторис можна до надсилання на погодження.")

def ensure_estimate_editable(order):
    """Кошторис складають під час діагностики; під час ремонту його доповнюють, якщо знайшли ще несправність."""
    if order.status not in DRAFT + ("in_repair",):
        fail(409, "Змінювати кошторис можна під час діагностики або ремонту, але не поки клієнт ухвалює рішення.")

def recheck_approval(order):
    """Під час ремонту доплату понад погоджену суму знову погоджує клієнт; зменшення суми згоди не потребує."""
    if order.status == "in_repair" and order.approved_total is not None:
        order.client_approval_status = "approved" if order.total_cost <= order.approved_total else "pending"

def stock_move(db, part, amount, user_id, reason, order_id=None):
    new_stock = part.quantity_in_stock + amount
    if new_stock < 0:
        fail(409, "На складі недостатньо запчастин.")
    part.quantity_in_stock = new_stock
    db.add(Movement(part_id=part.id, order_id=order_id, user_id=user_id, change_amount=amount,
                    stock_after=new_stock, reason=reason))

def lock_part(db, part_id):
    part = db.scalar(select(Part).where(Part.id == part_id).with_for_update())
    if not part:
        fail(404, "Запчастину не знайдено.")
    return part

def add_part(db, order, part, quantity, user_id):
    stock_move(db, part, -quantity, user_id, "Резервування для ремонту", order.id)
    db.add(OrderPart(order_id=order.id, part_id=part.id, part_name=part.name, quantity=quantity,
                     unit_cost_price=part.cost_price, unit_sale_price=part.sale_price,
                     total_sale_price=part.sale_price * quantity, spec_upgrade_target=part.spec_upgrade_target,
                     spec_upgrade_value=part.spec_upgrade_value))

def set_stage(db, order, new_status, user_id, comment=""):
    from .notifications import emit
    db.add(StatusHistory(order_id=order.id, changed_by_id=user_id, old_status=order.status,
                         new_status=new_status, comment=comment))
    order.status = new_status
    emit(db, "status", order.id)

def decide_estimate(db, order, user, approved, comment=""):
    """Фіксує рішення клієнта щодо кошторису (з кабінету, від адміністратора або з Telegram)."""
    from .notifications import emit
    if order.status != "waiting_approval" or order.client_approval_status != "pending":
        fail(409, "Заявка не очікує нового рішення.")
    order.client_approval_status = "approved" if approved else "rejected"
    if approved:
        order.approved_at = now()
        order.approved_total = order.total_cost
    # Відмова від доплати не скасовує раніше погоджену суму: ремонт можна продовжити в тому обсязі.
    order.approval_comment = comment
    emit(db, "decision", order.id)
    if user.role == "client":
        from .inbox import describe, notify_staff
        verdict = "погодив кошторис" if approved else "відхилив кошторис"
        notify_staff(db, order, "decision", f"Клієнт {verdict}: {describe(db, order)}" + (f". Коментар: {comment}" if comment else ""), user.id)
    if approved:  # однаково для клієнта й адміністратора, який записав згоду клієнта
        reason = "Клієнт погодив кошторис" if user.role == "client" else "Адміністратор записав згоду клієнта" + (f": {comment}" if comment else "")
        transition(db, order, "in_repair", user, reason)

def transition(db, order, target, user, comment):
    current = order.status
    if target not in ALLOWED.get(current, set()):
        fail(409, "Цей перехід між етапами недоступний.")
    if target == "diagnostics" and current == "registered" and not order.master_id:
        fail(409, "Спершу призначте відповідального майстра.")
    if target == "diagnostics" and current == "registered" and not access_device(db, order.device_id, user).serial_number:
        fail(409, "Перед діагностикою внесіть серійний номер пристрою.")
    if target == "cancelled" and repair_started(order) and not comment:
        fail(422, "Зазначте причину скасування ремонту.")
    if target == "diagnostics" and current == "waiting_approval":
        if order.client_approval_status == "approved":
            fail(409, "Погоджений кошторис зафіксовано.")
        if repair_started(order):
            fail(409, "Ремонт уже розпочато: змінюйте кошторис на етапі ремонту.")
        order.client_approval_status = "pending"
        order.approval_comment = ""
    if target == "waiting_approval":
        if not order.diagnostics:
            fail(409, "Спершу внесіть висновок діагностики.")
        if not works(db, order) and not parts(db, order):
            fail(409, "Кошторис порожній: додайте роботи або запчастини.")
        if current == "in_repair" and order.client_approval_status != "pending":
            fail(409, "Погоджувати нічого: сума кошторису не перевищує погоджену клієнтом.")
    if target == "in_repair" and order.client_approval_status != "approved":
        # Клієнт відмовився від доплати — ремонт продовжують у погодженому раніше обсязі.
        if not (order.client_approval_status == "rejected" and repair_started(order)):
            fail(409, "Клієнт ще не погодив вартість ремонту.")
    # Після початку ремонту деталі вже встановлено: на склад вони не повертаються.
    # Невикористані майстер прибирає з кошторису до скасування — тоді вони повертаються як звичайно.
    if target == "cancelled" and not repair_started(order):
        for item in sorted(parts(db, order), key=lambda item: item.part_id):
            stock_move(db, lock_part(db, item.part_id), item.quantity, user.id, "Повернення після скасування", order.id)
    if target == "returned":
        if current == "ready_for_pickup" and not comment:
            fail(422, "Зазначте, чому пристрій повертається без звичайної видачі.")
        if order.delivery_method == "nova_poshta" and not order.delivery_ttn:
            fail(409, "Клієнт обрав Нову Пошту: спершу внесіть номер накладної для повернення.")
        order.completed_at = now()  # дата закриття заявки; гарантії немає, бо ремонт не видано звичайним способом
    if target == "ready_for_pickup":
        if order.client_approval_status != "approved":
            fail(409, "Зміни в кошторисі ще не погоджено: надішліть кошторис клієнту або приберіть додаткові позиції.")
        device = access_device(db, order.device_id, user, lock=True)
        if order.diagnostics:
            device.known_defects_history = [
                *device.known_defects_history, f"{order.order_number}: {order.diagnostics}"
            ]
        for item in works(db, order):
            for field, value in item.updates_passport_spec.items():
                change_spec(db, device, field, value, user.id, item.work_name, order.id)
        for item in parts(db, order):
            if item.spec_upgrade_target and item.spec_upgrade_value:
                change_spec(db, device, item.spec_upgrade_target, item.spec_upgrade_value, user.id, item.part_name, order.id)
    if target == "completed":
        if order.paid_amount < order.total_cost:
            fail(409, "Перед завершенням облікуйте повну оплату замовлення.")
        if order.delivery_method == "nova_poshta" and not order.delivery_ttn:
            fail(409, "Клієнт обрав доставку Новою Поштою: спершу внесіть номер накладної.")
        order.completed_at = now()
        if order.warranty_days:
            order.warranty_expires_at = order.completed_at + timedelta(days=order.warranty_days)
    set_stage(db, order, target, user.id, comment)

def apply_delivery(delivery):
    """Перетворює блок доставки з форми на поля заявки."""
    return {"delivery_method": delivery.get("method", "pickup"), "delivery_city": delivery.get("city", ""),
            "delivery_branch": delivery.get("branch", "")}

NUMBERING_LOCK = 0x54440001  # ключ advisory-блокування PostgreSQL для нумерації заявок

def next_order_number(db):
    """TD-2026-0001: лічильник починається з одиниці щороку (рік — за київським часом)."""
    prefix = f"TD-{local_date(now()).year}-"
    if db.get_bind().dialect.name == "postgresql":
        # Дві одночасні заявки не отримають той самий номер: друга чекає, доки перша завершить транзакцію.
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": NUMBERING_LOCK})
    last = db.scalar(select(func.max(cast(func.substr(Order.order_number, len(prefix) + 1), Integer)))
                     .where(Order.order_number.like(prefix + "%")))
    return f"{prefix}{(last or 0) + 1:04d}"

def ensure_no_open_order(db, device):
    """Один пристрій — одна відкрита заявка: друге звернення додають до наявної або чекають її завершення."""
    db.execute(select(Device.id).where(Device.id == device.id).with_for_update())  # одночасні заявки на той самий пристрій
    number = db.scalar(select(Order.order_number).where(Order.device_id == device.id, Order.status.in_(ACTIVE)).limit(1))
    if number:
        fail(409, f"На цей пристрій уже є відкрита заявка {number}. Доповніть її або дочекайтеся завершення.")

def new_order(db, user, device, fields):
    ensure_no_open_order(db, device)
    fields = dict(fields)
    delivery = fields.pop("delivery", None) or {}
    fields.update(apply_delivery(delivery))
    order = Order(device_id=device.id, client_id=device.owner_id, order_number=next_order_number(db), **fields)
    db.add(order)
    db.flush()
    db.add(StatusHistory(order_id=order.id, changed_by_id=user.id, new_status="registered",
                         changed_at=order.created_at))
    from .notifications import emit
    emit(db, "status", order.id)
    if order.master_id:
        emit(db, "assigned", order.id)
    if user.role == "client":
        from .inbox import describe, notify_staff
        title = "Гарантійне звернення від клієнта" if order.warranty_claim else "Нова заявка від клієнта"
        notify_staff(db, order, "new", f"{title}: {describe(db, order)}", user.id)
    return order
