from datetime import timedelta
from decimal import Decimal
from sqlalchemy import func, select, text
from ..core.security import hasher
from ..models.models import Device, ModelPreset, Order, Part, Payment, Service, StatusHistory, User, Work, now
from .domain import STAGES, add_part, change_spec, estimate_items, new_order, refresh_totals, stock_move

PRESETS = [
    ("Ноутбук", "ASUS", "TUF Gaming F15 FX506HC", {"cpu":"Intel Core i5-11400H","ram":"8 GB DDR4","storage":"512 GB NVMe","gpu":"GeForce RTX 3050","display":"15,6″ · 144 Гц"}),
    ("Ноутбук", "Lenovo", "Legion 5 15ACH6H", {"cpu":"AMD Ryzen 7 5800H","ram":"16 GB DDR4","gpu":"GeForce RTX 3060","storage":"512 GB NVMe","display":"15,6″ · 165 Гц"}),
    ("Ноутбук", "Apple", "MacBook Air M2 A2681", {"cpu":"Apple M2","ram":"8 GB","storage":"256 GB SSD","display":"13,6″ Liquid Retina","os":"macOS"}),
    ("Ноутбук", "HP", "ProBook 450 G9", {"cpu":"Intel Core i5-1235U","ram":"16 GB DDR4","storage":"512 GB SSD"}),
    ("ПК", "TechDesk", "Робоча станція R5", {"cpu":"AMD Ryzen 5 5600","motherboard":"B550","ram":"16 GB DDR4","gpu":"Radeon RX 6600","psu":"550 Вт"}),
    ("ПК", "Dell", "OptiPlex 7010", {"cpu":"Intel Core i5-13500","ram":"16 GB DDR4","storage":"512 GB NVMe"}),
    ("Смартфон", "Apple", "iPhone 14 Pro 256 GB", {"storage":"256 GB","battery_health":"76%","display":"Super Retina XDR","color":"Темно-фіолетовий","os":"iOS"}),
    ("Смартфон", "Samsung", "Galaxy S23 Ultra", {"ram":"12 GB","storage":"256 GB","display":"Dynamic AMOLED 2X","color":"Чорний","os":"Android"}),
    ("Планшет", "Apple", "iPad Air 5", {"cpu":"Apple M1","storage":"64 GB","display":"10,9″ Liquid Retina","os":"iPadOS"}),
    ("Смарт-годинник", "Apple", "Watch Series 8 45 mm", {"case_size":"45 мм","case_material":"Алюміній","battery_health":"88%","seal":"Без слідів розкриття"}),
    ("Консоль", "Sony", "PlayStation 5 Disc", {"revision":"CFI-1216A","storage":"825 GB SSD","ports":"HDMI, USB-C, USB-A"}),
    ("Монітор", "LG", "UltraGear 27GN800", {"display":"27″ · 2560 × 1440 · 144 Гц","ports":"HDMI, DisplayPort"}),
    ("Міні-ПК", "ASUS", "ExpertCenter PN64", {"cpu":"Intel Core i5-12500H","ram":"16 GB DDR5","storage":"512 GB NVMe"}),
]

PARTS = [
    ("RAM-16D4", "Модуль пам’яті DDR4 16 GB", "Оперативна пам’ять", 9, 2, 690, 1090, "ram", "16 GB DDR4"),
    ("RAM-16D5", "Модуль пам’яті DDR5 16 GB", "Оперативна пам’ять", 7, 2, 1050, 1490, "ram", "16 GB DDR5"),
    ("SSD-1T", "Накопичувач NVMe 1 TB", "Накопичувачі", 8, 2, 1680, 2390, "storage", "1 TB NVMe"),
    ("SSD-512", "Накопичувач SATA 512 GB", "Накопичувачі", 5, 2, 790, 1190, "storage", "512 GB SATA SSD"),
    ("BAT-IP14P", "Акумулятор iPhone 14 Pro", "Акумулятори", 6, 2, 940, 1590, "battery_health", "100%"),
    ("BAT-MBA2", "Акумулятор MacBook Air M2", "Акумулятори", 1, 2, 1850, 2690, "battery_health", "100%"),
    ("FAN-F15", "Вентилятор ASUS TUF F15", "Охолодження", 4, 1, 370, 650, "", ""),
    ("FAN-L5", "Комплект вентиляторів Legion 5", "Охолодження", 1, 2, 710, 1090, "", ""),
    ("MX6-4G", "Термопаста Arctic MX-6", "Витратні матеріали", 16, 3, 170, 290, "", ""),
    ("DSP-14P", "Дисплей OLED iPhone 14 Pro", "Дисплеї", 3, 1, 3150, 4390, "", ""),
    ("DSP-IPS15", "Матриця IPS 15,6″", "Дисплеї", 4, 1, 1600, 2250, "", ""),
    ("USB-C-16", "Роз’єм живлення USB-C", "Роз’єми", 14, 4, 90, 230, "", ""),
    ("PSU-650", "Блок живлення 650 Вт", "Живлення", 6, 2, 1450, 2190, "psu", "650 Вт"),
    ("PS5-HDMI", "Роз’єм HDMI PlayStation 5", "Роз’єми", 2, 2, 230, 490, "", ""),
    ("PAD-1MM", "Термопрокладка 1 мм", "Витратні матеріали", 20, 5, 85, 160, "", ""),
]

SERVICES = [
    ("Діагностика ноутбука", 0), ("Чищення системи охолодження", 850), ("Заміна оперативної пам’яті", 550),
    ("Встановлення накопичувача", 650), ("Заміна акумулятора смартфона", 700), ("Заміна дисплейного модуля", 950),
    ("Відновлення роз’єму живлення", 1100), ("Налаштування операційної системи", 650), ("Заміна блока живлення", 580),
    ("Відновлення після залиття", 1400), ("Діагностика ігрової консолі", 0), ("Відновлення даних", 1200),
]

# демонстраційні оцінки клієнтів для завершених заявок (ключ — індекс пристрою)
REVIEWS = {0: (5, "Швидко додали пам’ять, ноутбук літає."), 1: (4, "Добре, але чекав на дзвінок довше, ніж обіцяли."),
           4: (5, "")}

def seed(db):
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(673229)"))
    if db.scalar(select(func.count(User.id))):
        return False
    accounts = [
        ("admin", "admin", "Коваленко Олександр", "Керівник сервісного центру"),
        ("master1", "master", "Іваненко Максим", "Ноутбуки, ПК та модернізація"),
        ("master2", "master", "Савченко Дмитро", "Смартфони, планшети та дисплеї"),
        ("master3", "master", "Мельник Артем", "Материнські плати й консолі"),
        ("client1", "client", "Бондаренко Олена", ""), ("client2", "client", "Шевченко Андрій", ""),
        ("client3", "client", "Ткаченко Ірина", ""), ("client4", "client", "Кравчук Віталій", ""),
    ]
    passwords = {role: hasher.hash(role + "123") for role in ("admin", "master", "client")}
    users = [User(email=f"{login}@techdesk.ua", phone=f"+380670000{index:03}", role=role,
                  full_name=name, specialization=specialization, password_hash=passwords[role])
             for index, (login, role, name, specialization) in enumerate(accounts, 1)]
    db.add_all(users)
    db.flush()
    for category, brand, model, specs in PRESETS:
        db.add(ModelPreset(device_category=category, brand=brand, model_name=model, default_specs=specs))
    devices = []
    for index, preset_index in enumerate((0, 6, 1, 2, 4, 8, 9, 10, 11)):
        category, brand, model, specs = PRESETS[preset_index]
        serial = "356287145902118" if index == 1 else f"TD-{brand[:3].upper()}-{10482 + index * 217}"
        device = Device(serial_number=serial, owner_id=users[4 + index % 4].id, device_category=category,
                        brand=brand, model=model, specifications=dict(specs),
                        cosmetic_condition="Незначні сліди використання, корпус без тріщин.")
        db.add(device)
        devices.append(device)
    inventory = []
    for sku, name, category, stock, minimum, cost, sale, field, value in PARTS:
        part = Part(sku=sku, name=name, category=category, min_stock_level=minimum, cost_price=cost,
                    sale_price=sale, spec_upgrade_target=field, spec_upgrade_value=value)
        db.add(part)
        db.flush()
        stock_move(db, part, stock, users[0].id, "Початкове оприбуткування")
        inventory.append(part)
    services = []
    for index, (name, price) in enumerate(SERVICES, 1):
        service = Service(code=f"SR-{index:03}", name=name, category="Ремонт і обслуговування",
                          default_price=price, estimated_hours=Decimal("1.5"), warranty_days=90 if price else 0)
        db.add(service)
        services.append(service)
    db.flush()
    examples = [
        (0, "completed", 1, 2, 0, 31, "Розширення оперативної пам’яті для роботи з графікою."),
        (1, "completed", 2, 4, 4, 16, "Смартфон вимикається при низькому заряді."),
        (4, "completed", 3, 8, 12, 9, "Комп’ютер перезавантажується під навантаженням."),
        (0, "waiting_approval", 1, 3, 2, 2, "Накопичувач працює нестабільно. Потрібно перевірити стан диска."),
        (1, "registered", None, None, None, 0, "Після падіння інколи пропадає зображення."),
        (2, "diagnostics", 1, 1, None, 3, "Ноутбук перегрівається під час роботи."),
        (3, "in_repair", 1, 4, 5, 4, "Акумулятор швидко розряджається."),
        (5, "ready_for_pickup", 2, 7, None, 5, "Потрібне відновлення налаштувань системи."),
        (7, "diagnostics", 3, None, None, 1, "Консоль не виводить зображення на екран."),
        (8, "registered", None, None, None, 0, "Мерехтіння дисплея на високій частоті."),
    ]
    for device_index, stage, master_index, service_index, part_index, age, description in examples:
        master = users[master_index] if master_index else None
        device = devices[device_index]
        order = new_order(db, users[0], device, dict(problem_description=description,
                          master_id=master.id if master else None, completeness="Пристрій і кабель живлення",
                          created_at=now() - timedelta(days=age)))
        if stage != "registered":
            order.diagnostics = "Несправність підтверджено. Перелік робіт і деталей наведено в кошторисі."
        if service_index is not None:
            service = services[service_index]
            db.add(Work(order_id=order.id, service_id=service.id, work_name=service.name,
                        master_id=order.master_id, price=service.default_price))
        if part_index is not None:
            part = inventory[part_index]
            add_part(db, order, part, 1, users[0].id)
            if stage == "completed" and part.spec_upgrade_target:
                change_spec(db, device, part.spec_upgrade_target, part.spec_upgrade_value, master.id,
                            "Модернізація під час ремонту", order.id)
        refresh_totals(db, order)
        if stage in STAGES[3:]:
            order.client_approval_status = "approved"
            order.approved_at = order.created_at + timedelta(hours=2)
            order.approved_total = order.total_cost
            order.approved_items = estimate_items(db, order)
        if stage == "completed":
            order.completed_at = order.created_at + timedelta(days=1)
            order.warranty_expires_at = order.completed_at + timedelta(days=90)
            order.paid_amount = order.total_cost
            if order.total_cost > 0:  # оплата — окремим записом, як під час звичайної видачі
                db.add(Payment(order_id=order.id, amount=order.total_cost, method=("cash", "card", "transfer")[device_index % 3],
                               created_by_id=order.master_id or users[0].id, created_at=order.completed_at))
            device.known_defects_history = [*device.known_defects_history, description]
            score, remark = REVIEWS[device_index]
            order.rating, order.rating_comment = score, remark
            order.rated_at = order.completed_at + timedelta(hours=5)
        if stage == "ready_for_pickup":
            order.delivery_method, order.delivery_city, order.delivery_branch = "nova_poshta", "Львів", "Відділення №12"
        order.status = stage  # після дат і оцінки: база перевіряє, що завершена заявка має дату завершення
        for step in range(1, STAGES.index(stage) + 1):
            db.add(StatusHistory(order_id=order.id, changed_by_id=order.master_id or users[0].id,
                                 old_status=STAGES[step-1], new_status=STAGES[step],
                                 changed_at=order.created_at + timedelta(hours=step)))
    db.commit()
    return True
