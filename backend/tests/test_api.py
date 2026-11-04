import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

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
    devices = request(client, customer, "GET", "/passports")
    existing = next(item for item in devices if item["warranty"])
    assert new_order(client, admin, existing["id"], is_warranty_case=True)["active_warranty"]["order_number"]
    assert len(request(client, admin, "GET", "/passports/presets")) >= 12

def test_repair_lifecycle_and_pdf(client, identities):
    admin, _ = identities["admin"]
    master, worker = identities["master"]
    customer, _ = identities["client"]
    other, _ = identities["other"]
    device = request(client, customer, "GET", "/passports?q=TD-ASU-10482")[0]
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
    customer, _ = identities["client"]
    device = request(client, customer, "GET", "/passports")[0]
    orders = [new_order(client, admin, device["id"]) for _ in range(2)]
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

def test_analytics_and_jsonb(client, identities):
    admin, _ = identities["admin"]
    analytics = request(client, admin, "GET", "/analytics/dashboard")
    orders = request(client, admin, "GET", "/orders")
    done = [order for order in orders if order["status"]=="completed"]
    assert analytics["revenue"] == sum(order["total_cost"] for order in done)
    assert analytics["profit"] == analytics["revenue"] - analytics["parts_cost"]
    assert sum(m["completed"] for m in analytics["staff"]) == len(done)
    assert analytics["active"] == len([o for o in orders if o["status"] not in ("completed","cancelled")])
    with engine.connect() as db:
        assert db.execute(text("SELECT pg_typeof(specifications)::text FROM devices LIMIT 1")).scalar() == "jsonb"
