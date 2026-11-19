import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from itertools import count

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

# A separate PostgreSQL database is required so tests exercise real row locks.
database_url = os.getenv("TEST_DATABASE_URL")
if not database_url:
    pytest.skip("Set TEST_DATABASE_URL to an empty PostgreSQL database ending in _test.", allow_module_level=True)
from sqlalchemy.engine import make_url
test_database = make_url(database_url)
if test_database.get_backend_name() != "postgresql" or not (test_database.database or "").endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must refer to a dedicated PostgreSQL *_test database")
os.environ["DATABASE_URL"] = database_url
os.environ["DEMO_MODE"] = "true"

from app.core.database import engine
from app.main import app

@pytest.fixture(scope="module")
def client():
    with engine.begin() as db:
        if db.execute(text("SELECT to_regclass('public.users')")).scalar():
            raise RuntimeError("Test database must be empty")
    command.upgrade(Config("alembic.ini"), "head")
    with TestClient(app) as browser:
        yield browser
    command.downgrade(Config("alembic.ini"), "base")
    with engine.begin() as db:
        db.execute(text("DROP TABLE IF EXISTS alembic_version"))

def login(client, role, account=None):
    response = client.post("/api/auth/login", json={"email": f"{account or role}@techdesk.ua", "password": role+"123"})
    assert response.status_code == 200, response.text
    result = response.json()
    return {"Authorization": "Bearer "+result["access_token"]}, result["user"]

@pytest.fixture(scope="module")
def identities(client):
    return {key: login(client, role, account) for key, role, account in [
        ("admin", "admin", None), ("master", "master", "master1"),
        ("client", "client", "client1"), ("other", "client", "client2"),
    ]}

def request(client, headers, method, path, data=None, status=200):
    response = client.request(method, "/api"+path, headers=headers, json=data)
    assert response.status_code == status, response.text
    return response.json()

def new_order(client, headers, device_id, **extra):
    return request(client, headers, "POST", "/orders", {"device_id":device_id,
                   "problem_description":"Потрібна перевірка і ремонт.", **extra}, 201)

_devices = count(1)

def fresh_device(client, admin, owner_id, **extra):
    """Окремий пристрій для тесту: на один пристрій дозволено лише одну відкриту заявку."""
    return request(client, admin, "POST", "/passports", {"serial_number": f"test-dev-{next(_devices):03d}", "owner_id": owner_id,
                   "device_category": "Ноутбук", "brand": "Test", "model": "Тестовий", **extra}, 201)

def finish(client, staff, path, amount):
    request(client, staff, "PATCH", path+"/status", {"status": "ready_for_pickup"})
    request(client, staff, "POST", path+"/payments", {"amount": amount, "method": "cash"}, 201)
    return request(client, staff, "PATCH", path+"/status", {"status": "completed"})

def device_with_warranty(client, admin, customer, owner_id):
    device = fresh_device(client, admin, owner_id)
    finish(client, admin, to_repair(client, admin, customer, device["id"], price="100.00"), "100.00")
    return device

def test_auth_and_permissions(client, identities):
    admin, admin_user = identities["admin"]
    customer, _ = identities["client"]
    assert request(client, admin, "GET", "/auth/me")["id"] == admin_user["id"]
    request(client, customer, "GET", "/analytics/dashboard", status=403)
    request(client, customer, "GET", "/warehouse/parts", status=403)
    assert client.get("/api/orders").status_code == 401
    assert client.post("/api/auth/login", json={"email":"admin@techdesk.ua","password":"incorrect"}).status_code == 401
    result = request(client, {}, "POST", "/auth/register", {
        "email":"demo-new@techdesk.ua","password":"demo-password","full_name":"Марія Тестова","phone":"+380501212121"
    }, 201)
    assert result["user"]["role"] == "client"
    assert "password_hash" not in result["user"]

def test_preset_passport_and_warranty(client, identities):
    admin, _ = identities["admin"]
    other, _ = identities["other"]
    customer, owner = identities["client"]
    preset = request(client, admin, "GET", "/passports/presets")[0]
    device = request(client, admin, "POST", "/passports", {
        "serial_number":"test-spec-001","owner_id":owner["id"],"device_category":preset["device_category"],
        "brand":preset["brand"],"model":preset["model_name"],"specifications":preset["default_specs"]
    }, 201)
    lookup = request(client, admin, "GET", "/passports/lookup-sn/test-spec-001")
    assert lookup["id"] == device["id"]
    assert lookup["specifications"] == preset["default_specs"]
    request(client, other, "GET", f"/passports/{device['id']}", status=404)
    existing = device_with_warranty(client, admin, customer, owner["id"])
    assert new_order(client, admin, existing["id"], is_warranty_case=True)["active_warranty"]["order_number"]
    assert len(request(client, admin, "GET", "/passports/presets")) >= 12

def test_repair_lifecycle_and_pdf(client, identities):
    admin, _ = identities["admin"]
    master, worker = identities["master"]
    customer, owner = identities["client"]
    other, _ = identities["other"]
    device = fresh_device(client, admin, owner["id"])
    order = new_order(client, admin, device["id"], master_id=worker["id"])
    path = f"/orders/{order['id']}"
    request(client, other, "GET", path, status=404)
    request(client, master, "PATCH", path+"/status", {"status":"diagnostics"})
    request(client, master, "PUT", path, {"diagnostics":"Зношений накопичувач.","internal_notes":"Внутрішня примітка"})
    request(client, master, "POST", path+"/works", {"work_name":"Встановлення диска","price":"750.00"}, 201)
    part = next(p for p in request(client, admin, "GET", "/warehouse/parts") if p["sku"]=="SSD-1T")
    reserved = request(client, master, "POST", path+"/parts", {"part_id":part["id"],"quantity":1}, 201)
    assert Decimal(str(reserved["total_cost"])) == Decimal(str(part["sale_price"])) + 750
    new_stock = next(p for p in request(client, admin, "GET", "/warehouse/parts") if p["id"]==part["id"])
    assert new_stock["quantity_in_stock"] == part["quantity_in_stock"]-1
    request(client, master, "POST", path+"/parts", {"part_id":part["id"],"quantity":999}, 409)
    fields = {key:part[key] for key in ("sku","name","category","compatible_device_category","min_stock_level","cost_price","sale_price","spec_upgrade_target","spec_upgrade_value")}
    request(client, admin, "PATCH", f"/warehouse/parts/{part['id']}", dict(fields, sale_price="9999.00"))
    assert request(client, admin, "GET", path)["total_cost"] == reserved["total_cost"]
    request(client, master, "PATCH", path+"/status", {"status":"waiting_approval"})
    request(client, master, "PATCH", path+"/status", {"status":"in_repair"}, 409)
    request(client, master, "POST", path+"/works", {"work_name":"Додаткова робота","price":"90.00"}, 409)
    estimate = request(client, customer, "GET", path)
    assert "internal_notes" not in estimate and "unit_cost_price" not in estimate["parts"][0]
    payload = {"approved": True, "expected_total": estimate["total_cost"], "estimate_version":estimate["estimate_version"]}
    request(client, customer, "POST", path+"/approve-cost", dict(payload, estimate_version="outdated"), 409)
    assert request(client, customer, "POST", path+"/approve-cost", payload)["status"] == "in_repair"
    request(client, master, "PATCH", path+"/status", {"status":"ready_for_pickup"})
    request(client, master, "PUT", path, {"paid_amount":estimate["total_cost"]})
    completed = request(client, master, "PATCH", path+"/status", {"status":"completed"})
    assert completed["warranty_expires_at"]
    live = request(client, customer, "GET", f"/passports/{device['id']}")
    assert live["specifications"]["storage"] == "1 TB NVMe"
    assert any(change["order_id"] == order["id"] and change["old_value"] != change["new_value"] for change in live["spec_history"])
    for kind in ("receipt","warranty"):
        response = client.get("/api"+path+"/pdf/"+kind, headers=customer)
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        assert response.content.startswith(b"%PDF")
    assert client.get(f"/api/passports/{device['id']}/qr", headers=customer).content.startswith(b"\x89PNG")
    assert client.get("/api/track", params={"code":order["order_number"]}).json() == {"status":"completed","label":"Завершена"}

def test_inventory_concurrent_reservation_and_return(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    orders = [new_order(client, admin, fresh_device(client, admin, owner["id"])["id"]) for _ in range(2)]
    part = request(client, admin, "POST", "/warehouse/parts", {
        "sku":"TEST-CONCURRENT", "name":"Деталь для тесту", "category":"Тестова", "quantity_in_stock":1,
        "cost_price":"40.00", "sale_price":"70.00"
    }, 201)
    def reserve(order):
        return client.post(f"/api/orders/{order['id']}/parts", headers=admin,
                           json={"part_id":part["id"],"quantity":1}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, orders))
    assert sorted(outcomes) == [201,409]
    winner = orders[outcomes.index(201)]
    request(client, admin, "PATCH", f"/orders/{winner['id']}/status", {"status":"cancelled"})
    assert request(client, admin, "GET", "/warehouse/parts?q=TEST-CONCURRENT")[0]["quantity_in_stock"] == 1

def to_repair(client, staff, customer, device_id, part_id=None, price="100.00", **extra):
    master_id = request(client, staff, "GET", "/users?role=master")[0]["id"]
    order = new_order(client, staff, device_id, master_id=master_id, **extra)
    path = f"/orders/{order['id']}"
    request(client, staff, "PATCH", path+"/status", {"status":"diagnostics"})
    request(client, staff, "PUT", path, {"diagnostics":"Потрібна заміна деталі."})
    request(client, staff, "POST", path+"/works", {"work_name":"Тестова робота","price":price}, 201)
    if part_id:
        request(client, staff, "POST", path+"/parts", {"part_id":part_id,"quantity":1}, 201)
    request(client, staff, "PATCH", path+"/status", {"status":"waiting_approval"})
    estimate = request(client, customer, "GET", path)
    request(client, customer, "POST", path+"/approve-cost", {"approved":True, "expected_total":estimate["total_cost"],
            "estimate_version":estimate["estimate_version"]})
    return path

def test_cancel_during_repair_keeps_installed_parts(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    device = fresh_device(client, admin, owner["id"])
    part = request(client, admin, "POST", "/warehouse/parts", {
        "sku":"TEST-CANCEL", "name":"Деталь для скасування", "category":"Тестова", "quantity_in_stock":2,
        "cost_price":"10.00", "sale_price":"20.00"}, 201)
    path = to_repair(client, admin, customer, device["id"], part["id"])
    assert request(client, admin, "GET", path)["status"] == "in_repair"
    request(client, admin, "PATCH", path+"/status", {"status":"cancelled"}, 422)
    cancelled = request(client, admin, "PATCH", path+"/status", {"status":"cancelled", "comment":"Клієнт забрав пристрій"})
    assert cancelled["status"] == "cancelled"
    # ремонт уже почався: встановлена деталь не повертається на склад
    assert request(client, admin, "GET", "/warehouse/parts?q=TEST-CANCEL")[0]["quantity_in_stock"] == 1
    # клієнт платить за виконане (погоджену суму); діагностика й неначаті ремонти безкоштовні
    assert Decimal(str(cancelled["amount_due"])) == Decimal(str(cancelled["approved_total"])) > 0
    request(client, admin, "PATCH", path+"/status", {"status":"returned"}, 422)
    paid = request(client, admin, "POST", path+"/payments", {"amount":str(cancelled["amount_due"]), "method":"card"}, 201)
    assert Decimal(str(paid["paid_amount"])) == Decimal(str(cancelled["amount_due"]))
    # скасований пристрій ще в сервісі — закриваємо заявку, коли його віддали
    returned = request(client, admin, "PATCH", path+"/status", {"status":"returned"})
    assert returned["status"] == "returned" and returned["completed_at"] and returned["warranty_expires_at"] is None
    request(client, admin, "PATCH", path+"/status", {"status":"cancelled"}, 409)

def test_completion_requires_payment(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    device = fresh_device(client, admin, owner["id"])
    path = to_repair(client, admin, customer, device["id"], price="300.00")
    request(client, admin, "PATCH", path+"/status", {"status":"ready_for_pickup"})
    request(client, admin, "PATCH", path+"/status", {"status":"completed"}, 409)
    request(client, admin, "PUT", path, {"paid_amount":"300.00"})
    assert request(client, admin, "PATCH", path+"/status", {"status":"completed"})["status"] == "completed"

def test_warranty_case_is_free_for_client(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    fresh = request(client, admin, "POST", "/passports", {
        "serial_number":"test-no-warranty","owner_id":owner["id"],"device_category":"Ноутбук",
        "brand":"Test","model":"Без гарантії"}, 201)
    request(client, admin, "POST", "/orders", {"device_id":fresh["id"], "problem_description":"Не вмикається.",
            "is_warranty_case":True}, 422)
    covered = device_with_warranty(client, admin, customer, owner["id"])
    order = new_order(client, admin, covered["id"], is_warranty_case=True)
    path = f"/orders/{order['id']}"
    request(client, admin, "PATCH", path+"/status", {"status":"diagnostics"}, 409)
    request(client, admin, "PUT", path, {"master_id":request(client, admin, "GET", "/users?role=master")[0]["id"]})
    request(client, admin, "PATCH", path+"/status", {"status":"diagnostics"})
    priced = request(client, admin, "POST", path+"/works", {"work_name":"Гарантійна заміна","price":"500.00"}, 201)
    assert Decimal(str(priced["works_total"])) == 500 and Decimal(str(priced["total_cost"])) == 0
    paid = request(client, admin, "PUT", path, {"is_warranty_case":False})
    assert Decimal(str(paid["total_cost"])) == 500

def test_login_rate_limit(client):
    attempt = {"email":"nobody@techdesk.ua", "password":"wrong-password"}
    codes = [client.post("/api/auth/login", json=attempt).status_code for _ in range(6)]
    assert codes == [401]*5 + [429]
    login(client, "admin")

class FakeTelegram:
    """Замість api.telegram.org: записує виклики, щоб перевірити повідомлення."""
    def __init__(self):
        self.calls = []

    def __call__(self, method, **params):
        # Як справжній Telegram: кнопки-посилання на localhost відхиляються разом із повідомленням.
        for row in (params.get("reply_markup") or {}).get("inline_keyboard", []):
            for button in row:
                if "url" in button and ("localhost" in button["url"] or "127.0.0.1" in button["url"]):
                    raise RuntimeError("Telegram sendMessage: Bad Request: inline keyboard button URL is invalid")
        self.calls.append((method, params))
        return {"message_id": len(self.calls)} if method == "sendMessage" else True

    def sent(self, chat_id):
        return [params for method, params in self.calls if method == "sendMessage" and params["chat_id"] == chat_id]

@pytest.fixture
def telegram_bot():
    from app.services import telegram
    fake = FakeTelegram()
    telegram.bot = telegram.Bot(fake, "techdesk_test_bot", background=False)
    yield telegram.bot, fake
    telegram.bot = None

def tg_message(chat_id, text, update_id=1):
    return {"update_id": update_id, "message": {"chat": {"id": chat_id, "type": "private"}, "text": text}}

def tg_press(chat_id, data):
    return {"update_id": 2, "callback_query": {"id": "query", "from": {"id": chat_id},
            "message": {"message_id": 10, "chat": {"id": chat_id}}, "data": data}}

def link_telegram(client, bot, headers, chat_id):
    url = request(client, headers, "POST", "/auth/telegram-link")["url"]
    assert url.startswith("https://t.me/techdesk_test_bot?start=")
    bot.handle_update(tg_message(chat_id, "/start " + url.split("start=")[1]))
    return url.split("start=")[1]

def test_telegram_notifications_and_approval(client, identities, telegram_bot):
    bot, fake = telegram_bot
    admin, _ = identities["admin"]
    master, worker = identities["master"]
    customer, _ = identities["client"]
    assert request(client, {}, "GET", "/auth/options")["telegram"] is True
    code = link_telegram(client, bot, customer, 7001)
    assert request(client, customer, "GET", "/auth/me")["telegram_linked"] is True
    assert "Готово" in fake.sent(7001)[-1]["text"]
    bot.handle_update(tg_message(7002, "/start " + code))
    assert "недійсне" in fake.sent(7002)[-1]["text"]
    link_telegram(client, bot, master, 7100)

    device = fresh_device(client, admin, identities["client"][1]["id"])
    order = new_order(client, admin, device["id"], master_id=worker["id"])
    path = f"/orders/{order['id']}"
    assert "Заявку прийнято" in fake.sent(7001)[-1]["text"]
    assert "призначено" in fake.sent(7100)[-1]["text"]
    request(client, master, "PATCH", path+"/status", {"status":"diagnostics"})
    request(client, master, "PUT", path, {"diagnostics":"Потрібна чистка системи охолодження."})
    request(client, master, "POST", path+"/works", {"work_name":"Чистка","price":"650.00"}, 201)
    request(client, master, "PATCH", path+"/status", {"status":"waiting_approval"})
    estimate = fake.sent(7001)[-1]
    assert "Кошторис готовий" in estimate["text"] and "650,00 грн" in estimate["text"]
    approve_button = estimate["reply_markup"]["inline_keyboard"][0][0]

    bot.handle_update(tg_press(9999, approve_button["callback_data"]))
    assert request(client, admin, "GET", path)["status"] == "waiting_approval"
    bot.handle_update(tg_press(7001, approve_button["callback_data"]))
    assert request(client, admin, "GET", path)["status"] == "in_repair"
    assert "Ремонт розпочато" in fake.sent(7001)[-1]["text"]
    assert "погодив" in fake.sent(7100)[-1]["text"]
    bot.handle_update(tg_press(7001, approve_button["callback_data"]))
    assert ("answerCallbackQuery", {"callback_query_id": "query", "text": "Заявка не очікує нового рішення."}) in fake.calls

    before = len(fake.sent(7001))
    bot.handle_update(tg_message(7001, "/orders"))
    listing = fake.sent(7001)[before]  # спершу список, далі кошториси, що чекають рішення
    assert listing["text"].startswith("Активні заявки") and order["order_number"] in listing["text"]
    assert request(client, customer, "DELETE", "/auth/telegram-link")["telegram_linked"] is False

def image_bytes(size=(2400, 1200), kind="PNG"):
    from io import BytesIO
    from PIL import Image
    stream = BytesIO()
    Image.new("RGB", size, (190, 40, 40)).save(stream, kind)
    return stream.getvalue()

def test_device_photos_and_label(client, identities):
    admin, _ = identities["admin"]
    customer, _ = identities["client"]
    other, _ = identities["other"]
    device = fresh_device(client, admin, identities["client"][1]["id"])
    base = f"/api/passports/{device['id']}/photos"
    upload = lambda headers, payload, **data: client.post(base, headers=headers, files={"file": payload}, data=data)
    response = upload(admin, ("front.png", image_bytes(), "image/png"), caption="Подряпина на кришці")
    assert response.status_code == 201, response.text
    photo = response.json()
    assert (photo["width"], photo["height"]) == (1600, 800)
    assert upload(admin, ("note.txt", b"not an image", "text/plain")).status_code == 422
    assert upload(customer, ("front.png", image_bytes(), "image/png")).status_code == 403
    order = new_order(client, admin, device["id"])
    linked = upload(admin, ("intake.jpg", image_bytes((800, 600), "JPEG"), "image/jpeg"), order_id=str(order["id"]))
    assert linked.status_code == 201, linked.text
    for_order = request(client, customer, "GET", f"/passports/{device['id']}/photos?order_id={order['id']}")
    assert [item["order_number"] for item in for_order] == [order["order_number"]]
    assert len(request(client, customer, "GET", f"/passports/{device['id']}/photos")) >= 2
    image = client.get(f"/api/photos/{photo['id']}", headers=customer)
    assert image.status_code == 200 and image.content.startswith(b"\xff\xd8")
    assert client.get(f"/api/photos/{photo['id']}", headers=other).status_code == 404
    label = client.get(f"/api/passports/{device['id']}/label", headers=customer)
    assert label.status_code == 200 and label.content.startswith(b"%PDF")
    request(client, admin, "DELETE", f"/photos/{photo['id']}")
    assert client.get(f"/api/photos/{photo['id']}", headers=customer).status_code == 404

def test_analytics_and_jsonb(client, identities):
    admin, _ = identities["admin"]
    analytics = request(client, admin, "GET", "/analytics/dashboard")
    orders = request(client, admin, "GET", "/orders")
    done = [order for order in orders if order["status"]=="completed"]
    returned = [order for order in orders if order["status"]=="returned"]
    # виручка: повна сума завершених ремонтів і фактичні оплати за повернутими без видачі
    assert analytics["revenue"] == sum(order["total_cost"] for order in done) + sum(order["paid_amount"] for order in returned)
    assert analytics["profit"] == analytics["revenue"] - analytics["parts_cost"]
    assert sum(m["completed"] for m in analytics["staff"]) == len(done)
    assert analytics["active"] == len([o for o in orders if o["status"] not in ("completed","cancelled","returned")])
    assert analytics["previous"] is None
    attention = analytics["attention"]
    assert {"stale", "waiting_approval", "low_stock"} <= set(attention)
    assert all(part["quantity"] <= part["minimum"] for part in attention["low_stock"])
    assert all(item["status"] in ("waiting_approval",) for item in attention["waiting_approval"])
    period = request(client, admin, "GET", "/analytics/dashboard?start=2026-01-01&end=2026-01-31")
    assert period["previous"]["start"] == "2025-12-01" and period["previous"]["end"] == "2025-12-31"
    assert all(order["stage_since"] for order in orders)
    with engine.connect() as db:
        assert db.execute(text("SELECT pg_typeof(specifications)::text FROM devices LIMIT 1")).scalar() == "jsonb"

def test_quick_request_without_registration(client, identities):
    admin, _ = identities["admin"]
    master, worker = identities["master"]
    payload = {"full_name": "Іван Швидкий", "phone": "050 777-88-99", "problem_description": "Не вмикається",
               "device": {"device_category": "Ноутбук", "brand": "ASUS", "model": "Zenbook 14"}}
    # приманка для ботів: заявка не створюється
    bot = client.post("/api/quick-request", json=dict(payload, website="http://spam"))
    assert bot.status_code == 201 and bot.json()["claim_token"] is None
    created = client.post("/api/quick-request", json=payload)
    assert created.status_code == 201, created.text
    result = created.json()
    assert result["claim_token"] and result["order_number"].startswith("TD-")
    # той самий телефон: нового кабінету не видаємо, токен не повторюється
    again = client.post("/api/quick-request", json=payload).json()
    assert again["claim_token"] is None and again["account_exists"]
    session = client.post("/api/auth/claim", json={"token": result["claim_token"]})
    assert session.status_code == 200 and session.json()["user"]["is_guest"]
    guest = {"Authorization": "Bearer " + session.json()["access_token"]}
    assert client.post("/api/auth/claim", json={"token": "x" * 24}).status_code == 404
    orders = request(client, guest, "GET", "/orders")
    assert {item["order_number"] for item in orders} >= {result["order_number"]}
    order_id = result["order_id"]
    # без серійного номера діагностику не розпочати
    request(client, admin, "PUT", f"/orders/{order_id}", {"master_id": worker["id"]})
    request(client, master, "POST", f"/orders/{order_id}/receive")  # клієнт приніс пристрій
    request(client, master, "PATCH", f"/orders/{order_id}/status", {"status": "diagnostics"}, 409)
    device_id = orders[-1]["device_id"] if "device_id" in orders[-1] else request(client, admin, "GET", f"/orders/{order_id}")["device_id"]
    request(client, master, "PATCH", f"/passports/{device_id}/serial", {"serial_number": "quick-sn-001"})
    request(client, master, "PATCH", f"/passports/{device_id}/serial", {"serial_number": "TD-ASU-10482"}, 409)
    request(client, master, "PATCH", f"/orders/{order_id}/status", {"status": "diagnostics"})
    # PDF та наліпка працюють і без пошти клієнта
    assert client.get(f"/api/passports/{device_id}/label", headers=admin).content.startswith(b"%PDF")
    assert client.get(f"/api/orders/{order_id}/pdf/receipt", headers=admin).content.startswith(b"%PDF")
    # завершення реєстрації
    done = request(client, guest, "POST", "/auth/complete-registration",
                   {"email": "Quick@Example.com", "password": "long-password"})
    assert done["email"] == "quick@example.com" and not done["is_guest"]
    request(client, guest, "POST", "/auth/complete-registration", {"email": "a@b.ua", "password": "long-password"}, 409)
    assert client.post("/api/auth/login", json={"email": "quick@example.com", "password": "long-password"}).status_code == 200

def test_staff_express_intake(client, identities):
    master, worker = identities["master"]
    customer, _ = identities["client"]
    request(client, customer, "POST", "/orders/intake", {"phone": "0509990011", "problem_description": "x" * 5,
            "device": {"device_category": "Смартфон", "brand": "Apple", "model": "iPhone 13"}}, 403)
    first = request(client, master, "POST", "/orders/intake", {
        "phone": "0509990011", "full_name": "Олена Прийомна", "problem_description": "Розбитий екран",
        "device": {"device_category": "Смартфон", "brand": "Apple", "model": "iPhone 13", "serial_number": "intake-001"},
    }, 201)
    assert first["claim_token"] and first["master_id"] == worker["id"]
    found = request(client, master, "GET", "/users/lookup?phone=%2B380509990011")
    assert found["is_guest"] and found["devices"][0]["serial_number"] == "INTAKE-001"
    # повторне звернення: наявний пристрій, нового кабінету немає; поки перша заявка відкрита, другу не створити
    repeat = {"device_id": found["devices"][0]["id"], "problem_description": "Не заряджається"}
    request(client, master, "POST", "/orders/intake", repeat, 409)
    request(client, master, "PATCH", f"/orders/{first['id']}/status", {"status": "cancelled"})
    request(client, master, "POST", "/orders/intake", repeat, 409)  # скасовано, але пристрій ще в сервісі
    request(client, master, "PATCH", f"/orders/{first['id']}/status", {"status": "returned"})
    second = request(client, master, "POST", "/orders/intake", repeat, 201)
    assert second["claim_token"] is None and second["client_id"] == found["id"]
    request(client, master, "POST", "/orders/intake", {"phone": "0509990011", "problem_description": "Помилка"}, 422)
    assert request(client, master, "GET", "/users/lookup?phone=0501110000") is None
    models = client.get("/api/public/models?q=asus").json()
    assert models and set(models[0]) == {"device_category", "brand", "model"}

def test_telegram_test_message_goes_to_own_chat(client, identities, telegram_bot):
    """Кожен користувач отримує тестове повідомлення лише у власний чат."""
    bot, fake = telegram_bot
    master, _ = identities["master"]
    customer, _ = identities["client"]
    request(client, customer, "POST", "/auth/telegram-test", None, 409)
    link_telegram(client, bot, customer, 8001)
    link_telegram(client, bot, master, 8100)
    request(client, customer, "POST", "/auth/telegram-test")
    request(client, master, "POST", "/auth/telegram-test")
    assert "клієнт" in fake.sent(8001)[-1]["text"] and "майстер" not in fake.sent(8001)[-1]["text"]
    assert "майстер" in fake.sent(8100)[-1]["text"]
    assert sum("Тестове" in m["text"] for m in fake.sent(8001)) == 1
    staff = request(client, identities["admin"][0], "GET", "/users")
    assert {u["full_name"] for u in staff if u["telegram_linked"]} >= {identities["client"][1]["full_name"], identities["master"][1]["full_name"]}

def test_password_change_and_admin_reset(client, identities):
    admin, _ = identities["admin"]
    person = request(client, admin, "POST", "/users", {"full_name": "Пароль Тестовий", "email": "pw@techdesk.ua",
                     "phone": "+380509998877", "password": "start-pass-1", "role": "client"}, 201)
    def sign_in(password, status=200):
        response = client.post("/api/auth/login", json={"email": "pw@techdesk.ua", "password": password})
        assert response.status_code == status, response.text
        return response.json()
    first = sign_in("start-pass-1")
    customer = {"Authorization": "Bearer " + first["access_token"]}
    assert "token_version" not in first["user"] and first["user"]["must_change_password"] is False
    request(client, customer, "POST", "/auth/password", {"current_password": "wrong-pass", "new_password": "new-secret-1"}, 400)
    changed = request(client, customer, "POST", "/auth/password", {"current_password": "start-pass-1", "new_password": "new-secret-1"})
    request(client, customer, "GET", "/auth/me", status=401)  # старий токен більше не діє
    fresh = {"Authorization": "Bearer " + changed["access_token"]}
    assert request(client, fresh, "GET", "/auth/me")["id"] == person["id"]
    sign_in("start-pass-1", 401)
    sign_in("new-secret-1")
    # скидання адміністратором: тимчасовий пароль, старі сеанси завершено, вимога змінити пароль
    request(client, fresh, "POST", f"/users/{person['id']}/reset-password", None, 403)
    reset = request(client, admin, "POST", f"/users/{person['id']}/reset-password")
    temporary = reset["temporary_password"]
    assert reset["user"]["must_change_password"] is True and len(temporary) == 14
    request(client, fresh, "GET", "/auth/me", status=401)
    login_result = sign_in(temporary)
    assert login_result["user"]["must_change_password"] is True
    session = {"Authorization": "Bearer " + login_result["access_token"]}
    # тимчасовий пароль відкриває лише зміну пароля: решту перевіряє сервер, а не лише інтерфейс
    request(client, session, "GET", "/orders", status=403)
    request(client, session, "GET", "/passports", status=403)
    assert request(client, session, "GET", "/auth/me")["must_change_password"] is True
    done = request(client, session, "POST", "/auth/password", {"current_password": temporary, "new_password": "final-pass-1"})
    assert done["user"]["must_change_password"] is False
    request(client, {"Authorization": "Bearer " + done["access_token"]}, "GET", "/orders")
    admin_id = request(client, admin, "GET", "/auth/me")["id"]
    request(client, admin, "POST", f"/users/{admin_id}/reset-password", None, 409)

def test_spec_suggestion_and_preset_from_intake(client, identities):
    master, _ = identities["master"]
    customer, _ = identities["client"]
    # пошук за словами в довільному порядку й регістрі
    names = {(m["brand"], m["model"]) for m in client.get("/api/public/models?q=f15 TUF").json()}
    assert ("ASUS", "TUF Gaming F15 FX506HC") in names
    preset = request(client, master, "GET", "/passports/spec-suggestion?category=Ноутбук&brand=asus&model=tuf gaming f15 fx506hc")
    assert preset["source"] == "preset" and preset["specifications"]
    request(client, customer, "GET", "/passports/spec-suggestion?category=Ноутбук&brand=asus&model=x", None, 403)
    unknown = "/passports/spec-suggestion?category=Ноутбук&brand=Acer&model=Swift Go 14"
    assert request(client, master, "GET", unknown) == {"source": None, "specifications": {}}
    specs = {"cpu": "Intel Core Ultra 5 125H", "ram": "16 ГБ LPDDR5X", "storage": "512 ГБ NVMe"}
    request(client, master, "POST", "/orders/intake", {"phone": "0631230001", "full_name": "Перший Власник",
            "problem_description": "Не заряджається", "device": {"device_category": "Ноутбук", "brand": "Acer",
            "model": "Swift Go 14", "specifications": specs}}, 201)
    from_device = request(client, master, "GET", unknown)
    assert from_device == {"source": "device", "specifications": specs}
    # друге приймання з позначкою «зберегти в довідник» — модель з’являється в довіднику й підказках
    request(client, master, "POST", "/orders/intake", {"phone": "0631230002", "full_name": "Другий Власник",
            "problem_description": "Чистка", "save_preset": True, "device": {"device_category": "Ноутбук",
            "brand": "Acer", "model": "Swift Go 14", "specifications": specs}}, 201)
    assert request(client, master, "GET", unknown)["source"] == "preset"
    assert any(m["model"] == "Swift Go 14" for m in client.get("/api/public/models?q=swift acer").json())

def unread(client, headers):
    return request(client, headers, "GET", "/notifications")

def test_client_cancel_and_staff_notifications(client, identities):
    admin, _ = identities["admin"]
    master, worker = identities["master"]
    customer, person = identities["client"]
    device = fresh_device(client, admin, identities["client"][1]["id"])
    before_admin, before_master = unread(client, admin)["unread"], unread(client, master)["unread"]
    order = new_order(client, customer, device["id"])  # заявка від клієнта — сповіщення працівникам
    after = unread(client, admin)
    assert after["unread"] == before_admin + 1 and after["items"][0]["order_number"] == order["order_number"]
    assert "Нова заявка" in after["items"][0]["text"] and unread(client, master)["unread"] == before_master + 1
    request(client, customer, "GET", "/notifications", status=403)
    # працівник не користується маршрутом клієнта; чужу заявку клієнт не бачить
    request(client, admin, "POST", f"/orders/{order['id']}/cancel", {}, 403)
    request(client, identities["other"][0], "POST", f"/orders/{order['id']}/cancel", {}, 404)
    done = request(client, customer, "POST", f"/orders/{order['id']}/cancel", {"comment": "Передумав"})
    assert done["status"] == "cancelled"
    assert request(client, admin, "GET", f"/orders/{order['id']}")["history"][-1]["comment"] == "Скасовано клієнтом: Передумав"
    assert "скасував" in unread(client, admin)["items"][0]["text"]
    request(client, customer, "POST", f"/orders/{order['id']}/cancel", {}, 409)
    # пристрій онлайн-заявки так і не надійшов: заявку закрито одразу, повертати нічого
    assert done["completed_at"] and not done["device_received_at"]
    request(client, admin, "PATCH", f"/orders/{order['id']}/status", {"status": "returned"}, 409)
    # після початку роботи скасувати може лише центр
    started = new_order(client, admin, device["id"], master_id=worker["id"])
    request(client, master, "PATCH", f"/orders/{started['id']}/status", {"status": "diagnostics"})
    request(client, customer, "POST", f"/orders/{started['id']}/cancel", {}, 409)
    # рішення клієнта щодо кошторису потрапляє майстру
    request(client, master, "PUT", f"/orders/{started['id']}", {"diagnostics": "Чистка"})
    request(client, master, "POST", f"/orders/{started['id']}/works", {"work_name": "Чистка", "price": "300.00"}, 201)
    request(client, master, "PATCH", f"/orders/{started['id']}/status", {"status": "waiting_approval"})
    estimate = request(client, customer, "GET", f"/orders/{started['id']}")
    request(client, customer, "POST", f"/orders/{started['id']}/approve-cost", {"approved": False, "expected_total": estimate["total_cost"],
            "estimate_version": estimate["estimate_version"], "comment": "Дорого"})
    latest = unread(client, master)["items"][0]
    assert "відхилив" in latest["text"] and "Дорого" in latest["text"]
    request(client, master, "POST", "/notifications/read", {"ids": [latest["id"]]})
    assert unread(client, master)["items"][0]["read"] is True
    request(client, master, "POST", "/notifications/read", {})
    assert unread(client, master)["unread"] == 0
    # після відмови від кошторису клієнт може скасувати заявку сам; деталей у кошторисі немає, ремонт не почався
    dropped = request(client, customer, "POST", f"/orders/{started['id']}/cancel", {"comment": "Дорого"})
    assert dropped["status"] == "cancelled" and "скасував" in unread(client, master)["items"][0]["text"]

def test_payments_methods_and_csv_export(client, identities):
    admin, _ = identities["admin"]
    customer, _ = identities["client"]
    device = fresh_device(client, admin, identities["client"][1]["id"])
    path = to_repair(client, admin, customer, device["id"], price="1000.00")
    request(client, admin, "POST", path+"/payments", {"amount": "100.00", "method": "cash"}, 409)  # ще в ремонті
    request(client, admin, "PATCH", path+"/status", {"status": "ready_for_pickup"})
    request(client, admin, "POST", path+"/payments", {"amount": "400.00", "method": "cash"}, 201)
    request(client, admin, "POST", path+"/payments", {"amount": "700.00", "method": "card"}, 422)  # більше за залишок
    request(client, admin, "POST", path+"/payments", {"amount": "600.00", "method": "bitcoin"}, 422)
    request(client, admin, "PATCH", path+"/status", {"status": "completed"}, 409)
    paid = request(client, admin, "POST", path+"/payments", {"amount": "600.00", "method": "card", "note": "Термінал"}, 201)
    assert Decimal(str(paid["paid_amount"])) == Decimal("1000") and [p["method"] for p in paid["payments"]] == ["cash", "card"]
    request(client, admin, "PUT", path, {"paid_amount": "500.00"}, 422)  # зменшити облік не можна
    request(client, admin, "PATCH", path+"/status", {"status": "completed"})
    methods = request(client, admin, "GET", "/analytics/dashboard")["payment_methods"]
    assert Decimal(methods["card"]) >= Decimal("600") and Decimal(methods["cash"]) >= Decimal("400")
    exported = client.get("/api/orders/export.csv?q=" + paid["order_number"], headers=admin)
    assert exported.status_code == 200 and exported.content.startswith("\ufeff".encode())
    text = exported.content.decode("utf-8-sig").splitlines()
    assert text[0].startswith("Номер;Створено;Клієнт") and len(text) == 2 and "1000,00" in text[1]
    assert client.get("/api/orders/export.csv", headers=customer).status_code == 403
    report = client.get("/api/analytics/export.csv", headers=admin).content.decode("utf-8-sig")
    assert "Картка;" in report and "Виручка, грн;" in report

def test_client_rates_completed_repair(client, identities):
    admin, _ = identities["admin"]
    master, worker = identities["master"]
    customer, _ = identities["client"]
    other, _ = identities["other"]
    device = fresh_device(client, admin, identities["client"][1]["id"])
    path = to_repair(client, admin, customer, device["id"], price="200.00")
    master_id = request(client, admin, "GET", path)["master_id"]
    request(client, customer, "POST", path+"/rating", {"rating": 5}, 409)  # ще не завершено
    request(client, admin, "PATCH", path+"/status", {"status": "ready_for_pickup"})
    request(client, admin, "POST", path+"/payments", {"amount": "200.00", "method": "card"}, 201)
    request(client, admin, "PATCH", path+"/status", {"status": "completed"})
    before = unread(client, admin)["unread"]
    request(client, admin, "POST", path+"/rating", {"rating": 5}, 403)   # працівник себе не оцінює
    request(client, other, "POST", path+"/rating", {"rating": 1}, 404)   # чужа заявка
    request(client, customer, "POST", path+"/rating", {"rating": 6}, 422)
    rated = request(client, customer, "POST", path+"/rating", {"rating": 4, "comment": "Швидко, але довго чекав дзвінка"})
    assert rated["rating"] == 4 and rated["rating_comment"].startswith("Швидко") and rated["rated_at"]
    request(client, customer, "POST", path+"/rating", {"rating": 5}, 409)  # оцінка одна
    assert unread(client, admin)["unread"] == before + 1
    assert "★★★★☆" in request(client, admin, "GET", "/notifications")["items"][0]["text"]
    stats = request(client, admin, "GET", "/analytics/dashboard")
    assert stats["rating"]["count"] >= 1 and stats["rating"]["distribution"]["4"] >= 1
    assert next(m for m in stats["staff"] if m["id"] == master_id)["rating"] is not None
    assert "Середня оцінка клієнтів" in client.get("/api/analytics/export.csv", headers=admin).content.decode("utf-8-sig")

def test_nova_poshta_delivery(client, identities, telegram_bot):
    bot, fake = telegram_bot
    admin, _ = identities["admin"]
    customer, _ = identities["client"]
    link_telegram(client, bot, customer, 7301)
    device = fresh_device(client, admin, identities["client"][1]["id"])
    request(client, customer, "POST", "/orders", {"device_id": device["id"], "problem_description": "Не заряджається",
            "delivery": {"method": "nova_poshta", "city": "Львів"}}, 422)  # без відділення
    path = to_repair(client, admin, customer, device["id"], price="500.00",
                     delivery={"method": "nova_poshta", "city": "Львів", "branch": "Відділення №12"})
    order = request(client, customer, "GET", path)
    assert (order["delivery_method"], order["delivery_city"]) == ("nova_poshta", "Львів")
    request(client, admin, "POST", path+"/shipment", {"ttn": "20450000000001"}, 409)  # ще в ремонті
    request(client, admin, "PATCH", path+"/status", {"status": "ready_for_pickup"})
    assert "відправку Новою Поштою" in fake.sent(7301)[-1]["text"]
    request(client, admin, "POST", path+"/shipment", {"ttn": "20450000000001"}, 409)  # не оплачено
    request(client, admin, "POST", path+"/payments", {"amount": "500.00", "method": "transfer"}, 201)
    request(client, admin, "PATCH", path+"/status", {"status": "completed"}, 409)  # немає ТТН
    request(client, admin, "POST", path+"/shipment", {"ttn": "12345"}, 422)
    shipped = request(client, admin, "POST", path+"/shipment", {"ttn": "2045 0000 0000 01"})
    assert shipped["delivery_ttn"] == "20450000000001"
    assert "cargo_number=20450000000001" in fake.sent(7301)[-1]["text"]
    request(client, customer, "PUT", path+"/delivery", {"method": "pickup"}, 409)  # уже відправлено
    assert request(client, admin, "PATCH", path+"/status", {"status": "completed"})["status"] == "completed"
    assert "Будемо вдячні за оцінку" in fake.sent(7301)[-1]["text"]
    exported = client.get("/api/orders/export.csv?q=" + order["order_number"], headers=admin).content.decode("utf-8-sig")
    assert "Нова Пошта: Львів" in exported and "20450000000001" in exported

def test_client_changes_delivery_before_shipping(client, identities):
    admin, _ = identities["admin"]
    customer, _ = identities["client"]
    device = fresh_device(client, admin, identities["client"][1]["id"])
    order = request(client, customer, "POST", "/orders", {"device_id": device["id"], "problem_description": "Шумить вентилятор"}, 201)
    assert order["delivery_method"] == "pickup"
    path = f"/orders/{order['id']}"
    before = unread(client, admin)["unread"]
    changed = request(client, customer, "PUT", path+"/delivery", {"method": "nova_poshta", "city": "Київ", "branch": "Поштомат №3301"})
    assert changed["delivery_branch"] == "Поштомат №3301" and unread(client, admin)["unread"] == before + 1
    request(client, admin, "POST", path+"/shipment", {"ttn": "20450000000002"}, 409)  # ще не відремонтовано
    back = request(client, customer, "PUT", path+"/delivery", {"method": "pickup", "city": "Київ", "branch": "x"})
    assert (back["delivery_method"], back["delivery_city"], back["delivery_branch"]) == ("pickup", "", "")

def test_telegram_menu_and_commands(client, identities, telegram_bot):
    bot, fake = telegram_bot
    master, _ = identities["master"]
    customer, _ = identities["client"]
    link_telegram(client, bot, customer, 7401)
    greeting = fake.sent(7401)[-1]
    keyboard = [button["text"] for row in greeting["reply_markup"]["keyboard"] for button in row]
    assert keyboard == ["📋 Мої заявки", "🛡 Гарантія", "➕ Нова заявка", "❓ Допомога", "🔕 Вимкнути сповіщення"]
    link_telegram(client, bot, master, 7402)
    assert [b["text"] for row in fake.sent(7402)[-1]["reply_markup"]["keyboard"] for b in row] == ["📋 Мої заявки", "❓ Допомога", "🔕 Вимкнути сповіщення"]
    # Кнопка меню надсилає текст, який бот розуміє як команду.
    bot.handle_update(tg_message(7401, "🛡 Гарантія"))
    assert "Гарантія діє" in fake.sent(7401)[-1]["text"] or "Чинних гарантій" in fake.sent(7401)[-1]["text"]
    bot.handle_update(tg_message(7401, "➕ Нова заявка"))
    assert "/orders/new" in fake.sent(7401)[-1]["text"]  # локальний сайт: посилання текстом, без кнопки
    bot.handle_update(tg_message(7401, "📋 Мої заявки"))
    assert "заявк" in fake.sent(7401)[-1]["text"].lower() or "заявк" in fake.sent(7401)[-2]["text"].lower()
    # Невідомий чат отримує довідку без меню.
    bot.handle_update(tg_message(7499, "привіт"))
    assert "Вітаємо" in fake.sent(7499)[-1]["text"] and "reply_markup" not in fake.sent(7499)[-1]

def test_telegram_mute_and_resume(client, identities, telegram_bot):
    bot, fake = telegram_bot
    admin, _ = identities["admin"]
    customer, _ = identities["client"]
    link_telegram(client, bot, customer, 7701)
    device = fresh_device(client, admin, identities["client"][1]["id"])
    bot.handle_update(tg_message(7701, "🔕 Вимкнути сповіщення"))
    reply = fake.sent(7701)[-1]
    assert "призупинено" in reply["text"]
    assert reply["reply_markup"]["keyboard"][-1][0]["text"] == "🔔 Увімкнути сповіщення"
    me = request(client, customer, "GET", "/auth/me")
    assert me["telegram_linked"] is True and me["telegram_muted"] is True  # чат не відв'язано
    before = len(fake.sent(7701))
    order = new_order(client, admin, device["id"])
    assert len(fake.sent(7701)) == before  # під час паузи сповіщення не надходять
    bot.handle_update(tg_message(7701, "📋 Мої заявки"))  # команди меню працюють і під час паузи
    assert order["order_number"] in fake.sent(7701)[before]["text"]
    bot.handle_update(tg_message(7701, "🔔 Увімкнути сповіщення"))
    assert "увімкнено" in fake.sent(7701)[-1]["text"]
    assert fake.sent(7701)[-1]["reply_markup"]["keyboard"][-1][0]["text"] == "🔕 Вимкнути сповіщення"
    request(client, admin, "PUT", f"/orders/{order['id']}", {"master_id": request(client, admin, "GET", "/users?role=master")[0]["id"]})
    request(client, admin, "PATCH", f"/orders/{order['id']}/status", {"status": "diagnostics"})
    assert "діагностиці" in fake.sent(7701)[-1]["text"]
    # Те саме із сайту
    assert request(client, customer, "PUT", "/auth/telegram-notifications", {"enabled": False})["telegram_muted"] is True
    assert request(client, customer, "PUT", "/auth/telegram-notifications", {"enabled": True})["telegram_muted"] is False
    request(client, customer, "DELETE", "/auth/telegram-link")
    request(client, customer, "PUT", "/auth/telegram-notifications", {"enabled": True}, 409)

def test_telegram_estimate_term_and_pending_list(client, identities, telegram_bot):
    bot, fake = telegram_bot
    admin, _ = identities["admin"]
    customer, _ = identities["client"]
    link_telegram(client, bot, customer, 7501)
    device = fresh_device(client, admin, identities["client"][1]["id"])
    master_id = request(client, admin, "GET", "/users?role=master")[0]["id"]
    path = f"/orders/{new_order(client, admin, device['id'], master_id=master_id)['id']}"
    request(client, admin, "PATCH", path+"/status", {"status": "diagnostics"})
    request(client, admin, "PUT", path, {"diagnostics": "Потрібна чистка."})
    service = request(client, admin, "GET", "/warehouse/services")[0]
    request(client, admin, "POST", path+"/works", {"service_id": service["id"]}, 201)
    request(client, admin, "PATCH", path+"/status", {"status": "waiting_approval"})
    assert "Орієнтовний строк" in fake.sent(7501)[-1]["text"]
    # «Мої заявки» повторно надсилає кошторис із кнопками погодження.
    bot.handle_update(tg_message(7501, "📋 Мої заявки"))
    assert "inline_keyboard" in fake.sent(7501)[-1]["reply_markup"]
    assert fake.sent(7501)[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"].startswith("ap:")

def test_telegram_warranty_and_maintenance_reminders(client, identities, telegram_bot):
    from datetime import timedelta
    from app.core.database import SessionLocal
    from app.models.models import Order, now
    bot, fake = telegram_bot
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    link_telegram(client, bot, customer, 7601)
    device = request(client, admin, "POST", "/passports", {"serial_number": "test-reminders", "owner_id": owner["id"],
                     "device_category": "Ноутбук", "brand": "Test", "model": "Нагадування"}, 201)
    path = to_repair(client, admin, customer, device["id"], price="300.00")
    request(client, admin, "PATCH", path+"/status", {"status": "ready_for_pickup"})
    request(client, admin, "POST", path+"/payments", {"amount": "300.00", "method": "cash"}, 201)
    done = request(client, admin, "PATCH", path+"/status", {"status": "completed"})
    with SessionLocal() as db:
        order = db.get(Order, done["id"])
        expires = order.warranty_expires_at
        order.created_at = order.completed_at = now() - timedelta(days=200)  # пристрій не повертався пів року
        db.commit()
    moment = expires - timedelta(days=3)
    assert bot.send_reminders(expires - timedelta(days=20)) == 0 or "Гарантія на ремонт" not in fake.sent(7601)[-1]["text"]
    bot.send_reminders(moment)
    texts = [m["text"] for m in fake.sent(7601)]
    assert any("Гарантія на ремонт закінчується" in t and done["order_number"] in t for t in texts)
    before = len(fake.sent(7601))
    bot.send_reminders(moment)  # повторно не надсилає
    assert len(fake.sent(7601)) == before
    with SessionLocal() as db:
        order = db.get(Order, done["id"])
        assert order.warranty_reminded_at is not None
        maintenance = order.maintenance_reminded_at
    assert maintenance is not None  # ноутбук пів року без візитів: порадили профілактику
    assert any("планову профілактику" in t for t in texts)
    # Якщо пристрій знову приносили після ремонту, профілактику не радимо.
    other = to_repair(client, admin, customer, device["id"], price="100.00")
    with SessionLocal() as db:
        order = db.get(Order, done["id"])
        order.maintenance_reminded_at = None
        db.commit()
    before = len(fake.sent(7601))
    bot.send_reminders(moment)
    assert all("профілактику" not in m["text"] for m in fake.sent(7601)[before:]) and other

def test_telegram_link_buttons_only_for_public_site(monkeypatch):
    from app.services import telegram
    monkeypatch.setattr(telegram, "PUBLIC_URL", "http://localhost:5173")
    text, buttons = telegram.with_link("Текст", "Відкрити", "/orders")
    assert buttons is None and "http://localhost:5173/orders" in text
    for local in ("http://127.0.0.1:5173", "http://192.168.1.20", "http://techdesk"):
        monkeypatch.setattr(telegram, "PUBLIC_URL", local)
        assert telegram.with_link("Т", "В", "/")[1] is None
    monkeypatch.setattr(telegram, "PUBLIC_URL", "https://techdesk.example.ua")
    text, buttons = telegram.with_link("Текст", "Відкрити", "/orders")
    assert text == "Текст" and buttons[0][0]["url"] == "https://techdesk.example.ua/orders"

def test_google_login(client, identities, monkeypatch):
    from app.api import auth as auth_module
    from app.services import google
    monkeypatch.setattr(auth_module, "GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
    claims = {"email": "Newbie@Gmail.com", "email_verified": True, "name": "Новий Клієнт"}
    def fake(credential):
        if credential.startswith("bad"):
            raise ValueError("bad token")
        return claims
    monkeypatch.setattr(google, "verify_credential", fake)
    token = "t" * 30
    assert request(client, {}, "GET", "/auth/options")["google_client_id"] == "test-client.apps.googleusercontent.com"
    # недійсний токен
    request(client, {}, "POST", "/auth/google", {"credential": "bad" + "x" * 30}, 401)
    # новий користувач: спершу просимо телефон
    first = request(client, {}, "POST", "/auth/google", {"credential": token})
    assert first["needs_phone"] is True and first["email"] == "newbie@gmail.com"
    created = request(client, {}, "POST", "/auth/google", {"credential": token, "phone": "+380671112233"})
    assert created["user"]["role"] == "client" and created["user"]["email"] == "newbie@gmail.com"
    # повторний вхід без телефону — той самий кабінет
    again = request(client, {}, "POST", "/auth/google", {"credential": token})
    assert again["user"]["id"] == created["user"]["id"]
    headers = {"Authorization": "Bearer " + again["access_token"]}
    assert request(client, headers, "GET", "/auth/me")["email"] == "newbie@gmail.com"
    # наявний кабінет за e-mail: Google не впускає автоматично, власник один раз підтверджує пароль
    admin, admin_user = identities["admin"]
    claims["email"] = admin_user["email"]
    assert request(client, {}, "POST", "/auth/google", {"credential": token})["needs_password"] is True
    request(client, {}, "POST", "/auth/google", {"credential": token, "password": "wrong-password"}, 401)
    linked = request(client, {}, "POST", "/auth/google", {"credential": token, "password": "admin123"})
    assert linked["user"]["id"] == admin_user["id"]
    # далі вхід через Google працює без пароля
    assert request(client, {}, "POST", "/auth/google", {"credential": token})["user"]["id"] == admin_user["id"]
    # клієнт не знає пароля (кабінет створено через Google до появи прив'язки): прив'язка зі скиданням пароля
    master, master_user = identities["master"]
    claims["email"] = master_user["email"]
    assert request(client, {}, "POST", "/auth/google", {"credential": token})["can_reset"] is False
    assert request(client, {}, "POST", "/auth/google", {"credential": token, "reset_password": True})["needs_password"] is True
    # робоча адреса на власному домені: її можуть перевидати іншій людині, тому скидання без пароля немає
    work = request(client, {}, "POST", "/auth/register", {"email": "google-work@techdesk.ua", "password": "unknown-pass",
                   "full_name": "Робоча пошта", "phone": "+380631234988"}, 201)
    claims["email"] = work["user"]["email"]
    assert request(client, {}, "POST", "/auth/google", {"credential": token})["can_reset"] is False
    assert request(client, {}, "POST", "/auth/google", {"credential": token, "reset_password": True})["needs_password"] is True
    request(client, {}, "POST", "/auth/login", {"email": "google-work@techdesk.ua", "password": "unknown-pass"})
    fresh = request(client, {}, "POST", "/auth/register", {"email": "google-old@gmail.com", "password": "unknown-pass",
                    "full_name": "Кабінет до прив'язки", "phone": "+380631234987"}, 201)
    old, client_user = {"Authorization": "Bearer " + fresh["access_token"]}, fresh["user"]
    claims["email"] = client_user["email"]
    assert request(client, {}, "POST", "/auth/google", {"credential": token})["can_reset"] is True
    reset = request(client, {}, "POST", "/auth/google", {"credential": token, "reset_password": True})
    assert reset["user"]["id"] == client_user["id"]
    request(client, old, "GET", "/auth/me", status=401)  # старі сеанси завершено
    assert request(client, {}, "POST", "/auth/google", {"credential": token})["user"]["id"] == client_user["id"]
    request(client, {}, "POST", "/auth/login", {"email": "google-old@gmail.com", "password": "unknown-pass"}, 401)
    # непідтверджена пошта відхиляється самою перевіркою, вимкнений акаунт — тут
    claims["email"] = "newbie@gmail.com"
    request(client, admin, "PATCH", f"/users/{created['user']['id']}", {"is_active": False, "specialization": ""})
    request(client, {}, "POST", "/auth/google", {"credential": token}, 401)
    # телефон, що вже є, не дозволяє створити другий кабінет
    claims["email"] = "second@gmail.com"
    request(client, {}, "POST", "/auth/google", {"credential": token, "phone": "+380671112233"}, 409)

def test_excel_exports(client, identities):
    import io
    from openpyxl import load_workbook
    admin, _ = identities["admin"]
    customer, _ = identities["client"]
    response = client.get("/api/orders/export.xlsx", headers=admin)
    assert response.status_code == 200 and response.headers["content-type"].startswith("application/vnd.openxml")
    ws = load_workbook(io.BytesIO(response.content)).active
    assert ws["A1"].value == "Номер" and ws.freeze_panes == "A2"
    phone = ws["D2"]
    assert isinstance(phone.value, str) and phone.number_format == "@"
    assert ws["B2"].is_date and isinstance(ws["L2"].value, (int, float))
    assert ws.column_dimensions["C"].width > 12
    assert client.get("/api/orders/export.xlsx", headers=customer).status_code == 403
    report = load_workbook(io.BytesIO(client.get("/api/analytics/export.xlsx", headers=admin).content)).active
    assert "Звіт TechDesk" in report["A1"].value
    assert any(row[0].value == "Майстри" for row in report.iter_rows())

def test_extra_work_during_repair(client, identities):
    """Під час ремонту знайшли ще несправність: доплату погоджує клієнт, відмова не зупиняє погоджений ремонт."""
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    device = fresh_device(client, admin, owner["id"])
    path = to_repair(client, admin, customer, device["id"], price="200.00")
    request(client, admin, "PATCH", path+"/status", {"status": "waiting_approval"}, 409)  # кошторис не змінювався
    extra = request(client, admin, "POST", path+"/works", {"work_name": "Заміна шлейфу", "price": "150.00"}, 201)
    assert extra["status"] == "in_repair" and extra["client_approval_status"] == "pending"
    request(client, admin, "PATCH", path+"/status", {"status": "ready_for_pickup"}, 409)  # доплату не погоджено
    request(client, admin, "PATCH", path+"/status", {"status": "waiting_approval"})
    request(client, admin, "PATCH", path+"/status", {"status": "diagnostics"}, 409)  # ремонт уже розпочато
    estimate = request(client, customer, "GET", path)
    assert Decimal(str(estimate["approved_total"])) == 200 and Decimal(str(estimate["total_cost"])) == 350
    refused = request(client, customer, "POST", path+"/approve-cost", {"approved": False, "expected_total": estimate["total_cost"],
                      "estimate_version": estimate["estimate_version"], "comment": "Лише основний ремонт"})
    assert refused["client_approval_status"] == "rejected" and Decimal(str(refused["approved_total"])) == 200
    request(client, customer, "POST", path+"/cancel", {}, 409)  # ремонт уже йде: скасовує лише центр
    # продовжуємо в погодженому обсязі: додаткову роботу прибрано, згода знову чинна
    request(client, admin, "PATCH", path+"/status", {"status": "in_repair"})
    extra_line = next(item for item in refused["works"] if item["work_name"] == "Заміна шлейфу")
    assert request(client, admin, "DELETE", f"{path}/works/{extra_line['id']}")["client_approval_status"] == "approved"
    # друга спроба: клієнт погоджує доплату
    request(client, admin, "POST", path+"/works", {"work_name": "Заміна шлейфу", "price": "150.00"}, 201)
    request(client, admin, "PATCH", path+"/status", {"status": "waiting_approval"})
    estimate = request(client, customer, "GET", path)
    agreed = request(client, customer, "POST", path+"/approve-cost", {"approved": True, "expected_total": estimate["total_cost"],
                     "estimate_version": estimate["estimate_version"]})
    assert agreed["status"] == "in_repair" and Decimal(str(agreed["approved_total"])) == 350
    assert request(client, admin, "PATCH", path+"/status", {"status": "ready_for_pickup"})["status"] == "ready_for_pickup"

def test_return_device_without_repair(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    device = fresh_device(client, admin, owner["id"])
    order = new_order(client, admin, device["id"], delivery={"method": "nova_poshta", "city": "Львів", "branch": "Відділення №1"})
    path = f"/orders/{order['id']}"
    request(client, admin, "PATCH", path+"/status", {"status": "returned"}, 409)  # спершу скасування
    request(client, admin, "PATCH", path+"/status", {"status": "cancelled"})
    request(client, admin, "PATCH", path+"/status", {"status": "returned"}, 409)  # Нова Пошта: потрібна накладна
    shipped = request(client, admin, "POST", path+"/shipment", {"ttn": "20450000000077"})  # ремонту не було — без оплати
    assert shipped["delivery_ttn"] == "20450000000077"
    assert request(client, admin, "PATCH", path+"/status", {"status": "returned"})["status"] == "returned"
    request(client, customer, "PUT", path+"/delivery", {"method": "pickup"}, 409)
    # готовий пристрій, за який клієнт відмовився платити
    other = to_repair(client, admin, customer, device["id"], price="100.00")
    request(client, admin, "PATCH", other+"/status", {"status": "ready_for_pickup"})
    revenue_before = Decimal(str(request(client, admin, "GET", "/analytics/dashboard")["revenue"]))
    request(client, admin, "POST", other+"/payments", {"amount": "40.00", "method": "cash"}, 201)  # часткова оплата
    request(client, admin, "PATCH", other+"/status", {"status": "returned"}, 422)  # потрібна причина
    done = request(client, admin, "PATCH", other+"/status", {"status": "returned", "comment": "Клієнт відмовився платити"})
    assert done["status"] == "returned" and done["warranty_expires_at"] is None
    # отримані гроші за повернутою заявкою потрапляють у виручку
    assert Decimal(str(request(client, admin, "GET", "/analytics/dashboard")["revenue"])) - revenue_before == Decimal("40")
    assert client.get("/api/track", params={"code": done["order_number"]}).json()["label"] == "Повернуто клієнту"

def test_one_open_order_numbering_and_admin_approval(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    device = fresh_device(client, admin, owner["id"])
    first = new_order(client, admin, device["id"])
    request(client, customer, "POST", "/orders", {"device_id": device["id"], "problem_description": "Ще одна проблема"}, 409)
    request(client, admin, "PATCH", f"/orders/{first['id']}/status", {"status": "cancelled"})
    request(client, admin, "PATCH", f"/orders/{first['id']}/status", {"status": "returned"})
    second = new_order(client, admin, device["id"])
    prefix, number = first["order_number"].rsplit("-", 1)
    assert second["order_number"] == f"{prefix}-{int(number) + 1:04d}"  # лічильник року, а не id заявки
    # публічний статус — лише за номером заявки, не за серійним номером із наліпки
    assert client.get("/api/track", params={"code": device["serial_number"]}).status_code == 404
    assert client.get("/api/track", params={"code": second["order_number"]}).status_code == 200
    path = f"/orders/{second['id']}"
    request(client, admin, "PUT", path, {"master_id": request(client, admin, "GET", "/users?role=master")[0]["id"]})
    request(client, admin, "PATCH", path+"/status", {"status": "diagnostics"})
    request(client, admin, "PUT", path, {"diagnostics": "Потрібна чистка."})
    request(client, admin, "PATCH", path+"/status", {"status": "waiting_approval"}, 409)  # порожній кошторис
    request(client, admin, "POST", path+"/works", {"work_name": "Чистка", "price": "100.00"}, 201)
    request(client, admin, "PATCH", path+"/status", {"status": "waiting_approval"})
    estimate = request(client, admin, "GET", path)
    by_phone = request(client, admin, "POST", path+"/approve-cost", {"approved": True, "expected_total": estimate["total_cost"],
                       "estimate_version": estimate["estimate_version"], "comment": "Погодив телефоном"})
    assert by_phone["status"] == "in_repair"  # так само, як після згоди клієнта в кабінеті

def test_device_owner_transfer(client, identities):
    admin, _ = identities["admin"]
    master, _ = identities["master"]
    customer, owner = identities["client"]
    other, buyer = identities["other"]
    device = fresh_device(client, admin, owner["id"])
    sold = new_order(client, admin, device["id"])
    transfer = f"/passports/{device['id']}/transfer"
    request(client, admin, "POST", transfer, {"owner_id": buyer["id"]}, 409)  # відкрита заявка
    request(client, admin, "PATCH", f"/orders/{sold['id']}/status", {"status": "cancelled"})
    request(client, admin, "POST", transfer, {"owner_id": buyer["id"]}, 409)  # скасовано, але пристрій ще в сервісі
    request(client, admin, "PATCH", f"/orders/{sold['id']}/status", {"status": "returned"})
    request(client, master, "POST", transfer, {"owner_id": buyer["id"]}, 403)
    request(client, admin, "POST", transfer, {"owner_id": owner["id"]}, 409)  # той самий власник
    moved = request(client, admin, "POST", transfer, {"owner_id": buyer["id"], "reason": "Продав пристрій"})
    assert moved["owner_id"] == buyer["id"] and moved["spec_history"][0]["field_name"] == "owner"
    request(client, customer, "GET", f"/passports/{device['id']}", status=404)
    seen = request(client, other, "GET", f"/passports/{device['id']}")
    assert seen["spec_history"][0]["old_value"] == "попередній власник" and seen["orders"] == []
    assert new_order(client, other, device["id"])["client_id"] == buyer["id"]

def test_client_warranty_claim(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    plain = fresh_device(client, admin, owner["id"])
    claim = {"problem_description": "Знову не працює", "warranty_claim": True}
    request(client, customer, "POST", "/orders", dict(claim, device_id=plain["id"]), 422)  # гарантії немає
    covered = device_with_warranty(client, admin, customer, owner["id"])
    order = request(client, customer, "POST", "/orders", dict(claim, device_id=covered["id"]), 201)
    assert order["warranty_claim"] is True and order["is_warranty_case"] is False  # рішення за працівником
    assert "Гарантійне звернення" in unread(client, admin)["items"][0]["text"]
    decided = request(client, admin, "PUT", f"/orders/{order['id']}", {"is_warranty_case": True})
    assert decided["is_warranty_case"] is True and Decimal(str(decided["total_cost"])) == 0

# ---- Виправлення за результатами аудиту ----

def test_hardcoded_demo_key_no_longer_signs_tokens(client, identities):
    import jwt
    from datetime import timedelta
    from app.models.models import now
    _, admin_user = identities["admin"]
    forged = jwt.encode({"sub": str(admin_user["id"]), "ver": 0, "exp": now() + timedelta(hours=1)},
                        "techdesk-local-demo-key-change-me-32-chars", algorithm="HS256")
    assert client.get("/api/users", headers={"Authorization": "Bearer " + forged}).status_code == 401

def test_any_change_after_approval_needs_new_consent(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    path = to_repair(client, admin, customer, fresh_device(client, admin, owner["id"])["id"], price="500.00")
    original = request(client, admin, "GET", path)["works"][0]
    request(client, admin, "DELETE", f"{path}/works/{original['id']}")
    swapped = request(client, admin, "POST", path+"/works", {"work_name": "Зовсім інша робота", "price": "500.00"}, 201)
    assert swapped["client_approval_status"] == "pending"  # та сама сума, але інший склад
    request(client, admin, "PATCH", path+"/status", {"status": "ready_for_pickup"}, 409)
    # повернули погоджений склад — попередня згода знову чинна
    request(client, admin, "DELETE", f"{path}/works/{swapped['works'][0]['id']}")
    restored = request(client, admin, "POST", path+"/works", {"work_name": "Тестова робота", "price": "500.00"}, 201)
    assert restored["client_approval_status"] == "approved"
    # дописати висновок діагностики можна без нової згоди
    assert request(client, admin, "PUT", path, {"diagnostics": "Додатково: почищено вентилятор."})["client_approval_status"] == "approved"
    # зменшення суми теж змінює склад: клієнт погоджує нову суму
    cheaper = request(client, admin, "PATCH", f"{path}/works/{restored['works'][0]['id']}", {"work_name": "Тестова робота", "price": "300.00"})
    assert cheaper["client_approval_status"] == "pending"
    request(client, admin, "PATCH", path+"/status", {"status": "waiting_approval"})
    estimate = request(client, customer, "GET", path)
    agreed = request(client, customer, "POST", path+"/approve-cost", {"approved": True, "expected_total": estimate["total_cost"],
                     "estimate_version": estimate["estimate_version"]})
    assert Decimal(str(agreed["approved_total"])) == 300 and agreed["status"] == "in_repair"

def test_cancelled_order_keeps_device_in_service(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    device = fresh_device(client, admin, owner["id"])
    order = new_order(client, admin, device["id"])
    request(client, admin, "PATCH", f"/orders/{order['id']}/status", {"status": "cancelled"})
    request(client, customer, "POST", "/orders", {"device_id": device["id"], "problem_description": "Ще раз"}, 409)
    request(client, admin, "PATCH", f"/orders/{order['id']}/status", {"status": "returned"})
    new_order(client, customer, device["id"])

def test_master_works_only_with_own_orders(client, identities):
    admin, _ = identities["admin"]
    master, worker = identities["master"]
    _, owner = identities["client"]
    order = new_order(client, admin, fresh_device(client, admin, owner["id"])["id"])
    path = f"/orders/{order['id']}"
    request(client, master, "PATCH", path+"/status", {"status": "cancelled"}, 403)  # вільну заявку спершу беруть
    request(client, master, "POST", path+"/works", {"work_name": "Чужа робота", "price": "10.00"}, 403)
    request(client, master, "PUT", path, {"master_id": worker["id"], "internal_notes": "разом із взяттям"}, 403)
    assert request(client, master, "PUT", path, {"master_id": worker["id"]})["master_id"] == worker["id"]
    request(client, master, "PATCH", path+"/status", {"status": "diagnostics"})
    request(client, admin, "PUT", path, {"master_id": None}, 409)  # після початку діагностики — лише передати іншому

def test_serial_number_changes_are_logged(client, identities):
    admin, _ = identities["admin"]
    master, _ = identities["master"]
    _, owner = identities["client"]
    device = fresh_device(client, admin, owner["id"])
    edited = request(client, master, "PUT", f"/passports/{device['id']}", {"serial_number": "audit-sn-new", "device_category": "Ноутбук",
                     "brand": "Test", "model": "Тестовий"})
    entry = next(h for h in edited["spec_history"] if h["field_name"] == "serial_number")
    assert (entry["old_value"], entry["new_value"]) == (device["serial_number"], "AUDIT-SN-NEW")

def test_client_cannot_mark_own_order_urgent(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    device = fresh_device(client, admin, owner["id"])
    order = request(client, customer, "POST", "/orders", {"device_id": device["id"], "problem_description": "Терміново!", "priority": "urgent"}, 201)
    assert order["priority"] == "normal"

def test_deactivation_ends_sessions_for_good(client, identities):
    admin, _ = identities["admin"]
    person = request(client, admin, "POST", "/users", {"full_name": "Звільнений Працівник", "email": "fired@techdesk.ua",
                     "phone": "+380509990102", "password": "start-pass-1", "role": "master"}, 201)
    login_result = client.post("/api/auth/login", json={"email": "fired@techdesk.ua", "password": "start-pass-1"}).json()
    session = {"Authorization": "Bearer " + login_result["access_token"]}
    request(client, admin, "PATCH", f"/users/{person['id']}", {"is_active": False, "specialization": ""})
    request(client, admin, "PATCH", f"/users/{person['id']}", {"is_active": True, "specialization": ""})
    request(client, session, "GET", "/auth/me", status=401)

def test_oversized_photo_rejected_before_decoding(client, identities):
    from io import BytesIO
    from PIL import Image
    admin, _ = identities["admin"]
    _, owner = identities["client"]
    device = fresh_device(client, admin, owner["id"])
    stream = BytesIO()
    Image.new("1", (9500, 9500)).save(stream, "PNG")  # кілька кілобайтів, але 90 мегапікселів
    response = client.post(f"/api/passports/{device['id']}/photos", headers=admin,
                           files={"file": ("big.png", stream.getvalue(), "image/png")})
    assert response.status_code == 413

def test_quick_request_does_not_reveal_other_devices(client, identities):
    _, owner = identities["client"]
    base = {"full_name": "Хтось Сторонній", "problem_description": "Перевірка",
            "device": {"device_category": "Ноутбук", "brand": "ASUS", "model": "X", "serial_number": "TD-ASU-10482"}}
    foreign = client.post("/api/quick-request", headers={"X-Real-IP": "10.20.0.1"}, json=dict(base, phone="0991112233"))
    owners = client.post("/api/quick-request", headers={"X-Real-IP": "10.20.0.2"}, json=dict(base, phone=owner["phone"]))
    assert foreign.status_code == owners.status_code == 409
    assert foreign.json()["detail"] == owners.json()["detail"] and "TD-" not in owners.json()["detail"]

def test_guest_gets_clear_message_when_registering(client):
    quick = client.post("/api/quick-request", headers={"X-Real-IP": "10.20.0.3"}, json={"full_name": "Гість Реєстрація",
                        "phone": "0997770012", "problem_description": "Тест",
                        "device": {"device_category": "ДБЖ", "brand": "APC", "model": "Back"}})
    assert quick.status_code == 201
    response = client.post("/api/auth/register", headers={"X-Real-IP": "10.20.0.4"}, json={"email": "guest-reg@example.com",
                           "password": "long-pass-1", "full_name": "Гість Реєстрація", "phone": "0997770012"})
    assert response.status_code == 409 and "особистим посиланням" in response.json()["detail"]

def test_quick_request_for_other_device(client):
    """Пристрій поза переліком категорій приймається як «Інше», а невідома категорія відхиляється."""
    base = {"full_name": "Гість Принтер", "phone": "0997770031", "problem_description": "Не захоплює папір"}
    other = client.post("/api/quick-request", headers={"X-Real-IP": "10.20.0.5"},
                        json=dict(base, device={"device_category": "Інше", "brand": "HP", "model": "LaserJet 1020"}))
    assert other.status_code == 201
    unknown = client.post("/api/quick-request", headers={"X-Real-IP": "10.20.0.6"},
                          json=dict(base, phone="0997770032", device={"device_category": "Принтер", "brand": "HP", "model": "X"}))
    assert unknown.status_code == 422

def test_online_request_waits_for_device(client, identities):
    """Онлайн-заявку не можна взяти в роботу й видати квитанцію, доки пристрій не надійшов до центру."""
    admin, _ = identities["admin"]
    created = client.post("/api/quick-request", headers={"X-Real-IP": "10.20.0.7"}, json={
        "full_name": "Гість Пошта", "phone": "0997770041", "problem_description": "Не вмикається",
        "device": {"device_category": "Ноутбук", "brand": "Acer", "model": "Aspire 5"}})
    assert created.status_code == 201
    path = f"/orders/{created.json()['order_id']}"
    assert request(client, admin, "GET", path)["device_received_at"] is None
    blocked = request(client, admin, "PATCH", path+"/status", {"status": "diagnostics"}, 409)
    assert "не надійшов" in blocked["detail"]
    assert client.get("/api"+path+"/pdf/receipt", headers=admin).status_code == 409
    assert request(client, admin, "POST", path+"/receive")["device_received_at"]
    request(client, admin, "POST", path+"/receive", status=409)
    assert client.get("/api"+path+"/pdf/receipt", headers=admin).content.startswith(b"%PDF")

def test_database_enforces_integrity(client, identities):
    """Правила цілісності діють у самій базі, а не лише в коді API (міграція 0012)."""
    from sqlalchemy.exc import IntegrityError
    # демодані: «оплачено» у завершених заявках збігається з журналом оплат
    with engine.connect() as db:
        mismatched = db.execute(text("""
            SELECT count(*) FROM repair_orders o
            WHERE o.paid_amount <> COALESCE((SELECT sum(amount) FROM payments p WHERE p.order_id = o.id), 0)""")).scalar()
        assert mismatched == 0
        assert db.execute(text("SELECT count(*) FROM payments")).scalar() > 0
    broken = [
        "UPDATE repair_orders SET total_cost = total_cost + 1 WHERE is_warranty_case = false",
        "UPDATE repair_orders SET priority = 'whenever'",
        "UPDATE repair_orders SET rating = 5 WHERE status = 'registered'",
        "UPDATE repair_orders SET completed_at = NULL WHERE status = 'completed'",
        "UPDATE repair_orders SET delivery_method = 'nova_poshta', delivery_city = '' WHERE status = 'registered'",
        "UPDATE order_status_history SET new_status = 'lost'",
        "UPDATE order_parts SET total_sale_price = total_sale_price + 1",
        # друга відкрита заявка на той самий пристрій
        """INSERT INTO repair_orders (order_number, device_id, client_id, status, priority, problem_description, completeness,
               cosmetic_notes, diagnostics, internal_notes, is_warranty_case, works_total, parts_total, total_cost, paid_amount,
               client_approval_status, approval_comment, warranty_days, created_at, updated_at)
           SELECT 'TD-TEST-9999', device_id, client_id, 'registered', 'normal', 'Дубль', '', '', '', '', false, 0, 0, 0, 0,
               'pending', '', 0, now(), now()
           FROM repair_orders WHERE status NOT IN ('completed', 'returned') LIMIT 1""",
    ]
    for statement in broken:
        with pytest.raises(IntegrityError):
            with engine.begin() as db:
                db.execute(text(statement))


def test_cancel_without_started_repair_is_free(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    device = fresh_device(client, admin, owner["id"])
    master_id = request(client, admin, "GET", "/users?role=master")[0]["id"]
    order = new_order(client, admin, device["id"], master_id=master_id)
    path = f"/orders/{order['id']}"
    request(client, admin, "PATCH", path+"/status", {"status":"diagnostics"})
    request(client, admin, "PUT", path, {"diagnostics":"Потрібна заміна плати."})
    request(client, admin, "POST", path+"/works", {"work_name":"Заміна плати","price":"900.00"}, 201)
    request(client, admin, "PATCH", path+"/status", {"status":"waiting_approval"})
    estimate = request(client, customer, "GET", path)
    request(client, customer, "POST", path+"/approve-cost", {"approved":False, "expected_total":estimate["total_cost"],
            "estimate_version":estimate["estimate_version"], "comment":"Дорого"})
    cancelled = request(client, customer, "POST", path+"/cancel", {"comment":"Заберу так"})
    # діагностика безкоштовна: після відмови від кошторису платити нічого
    assert Decimal(str(cancelled["amount_due"])) == 0
    request(client, admin, "POST", path+"/payments", {"amount":"100.00", "method":"cash"}, 409)
    assert request(client, admin, "PATCH", path+"/status", {"status":"returned"})["status"] == "returned"

def test_deactivated_master_releases_orders(client, identities):
    admin, _ = identities["admin"]
    customer, owner = identities["client"]
    created = request(client, admin, "POST", "/users", {"full_name":"Тимчасовий майстер", "email":"temp.master@techdesk.ua",
                      "phone":"+380639876543", "password":"TempMaster-2026", "role":"master"}, 201)
    device = fresh_device(client, admin, owner["id"])
    order = new_order(client, admin, device["id"], master_id=created["id"])
    path = f"/orders/{order['id']}"
    request(client, admin, "PATCH", path+"/status", {"status":"diagnostics"})
    result = request(client, admin, "PATCH", f"/users/{created['id']}", {"is_active":False, "specialization":""})
    assert result["released_orders"] == [order["order_number"]]
    assert request(client, admin, "GET", path)["master_id"] is None
    # звільнену заявку бере інший майстер і продовжує роботу
    master, worker = identities["master"]
    taken = request(client, master, "PUT", path, {"master_id":worker["id"]})
    assert taken["master_id"] == worker["id"]

def test_forgot_password_by_mail(client, identities):
    import re
    from app.services import mail
    admin, _ = identities["admin"]
    request(client, admin, "POST", "/users", {"full_name": "Забудько", "email": "forgot.me@gmail.com",
            "phone": "+380631231234", "password": "old-pass-123", "role": "client"}, 201)
    mail.sent.clear()
    # відповідь однакова для відомої й невідомої пошти; лист іде лише власнику кабінету
    unknown = client.post("/api/auth/forgot", json={"email": "nobody.here@gmail.com"}).json()
    known = client.post("/api/auth/forgot", json={"email": "Forgot.Me@gmail.com"}).json()
    assert unknown == known and len(mail.sent) == 1 and mail.sent[0]["To"] == "forgot.me@gmail.com"
    link = re.search(r"/reset\?token=(\S+)", mail.sent[0].get_content()).group(1)
    old = client.post("/api/auth/login", json={"email": "forgot.me@gmail.com", "password": "old-pass-123"}).json()["access_token"]
    request(client, {}, "POST", "/auth/reset", {"token": "x" * 30, "new_password": "new-pass-456"}, 400)
    done = request(client, {}, "POST", "/auth/reset", {"token": link, "new_password": "new-pass-456"})
    assert done["access_token"]
    # посилання одноразове, старий пароль і старі сеанси більше не діють
    request(client, {}, "POST", "/auth/reset", {"token": link, "new_password": "other-pass-789"}, 400)
    assert client.post("/api/auth/login", json={"email": "forgot.me@gmail.com", "password": "old-pass-123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "forgot.me@gmail.com", "password": "new-pass-456"}).status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer " + old}).status_code == 401
