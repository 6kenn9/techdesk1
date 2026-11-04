from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from .api import analytics, auth, orders, passports, pdf_generator, warehouse
from .core.config import DEMO_MODE
from .core.database import SessionLocal
from .core.security import Db, fail
from .models.models import Device, Order
from .services.domain import LABELS

@asynccontextmanager
async def lifespan(app):
    if DEMO_MODE:
        from .services.seed_service import seed
        with SessionLocal() as session:
            seed(session)
    yield

app = FastAPI(title="TechDesk — API сервісного центру", version="1.0.0", lifespan=lifespan)
for module in (auth, passports, orders, warehouse, analytics, pdf_generator):
    app.include_router(module.router)

@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": "Перевірте заповнення полів і допустимі значення."})

@app.exception_handler(IntegrityError)
async def conflict_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": "Запис із такими реквізитами вже існує або порушує зв’язок даних."})

@app.get("/api/health")
def health(db: Db):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

@app.get("/api/track")
def track(code: str, db: Db):
    value = code.strip().upper()
    if not 2 <= len(value) <= 80:
        fail(422, "Введіть номер заявки або серійний номер.")
    order = db.scalar(select(Order).join(Device, Device.id == Order.device_id).where(
        or_(Order.order_number == value, Device.serial_number == value)).order_by(Order.id.desc()).limit(1))
    if not order:
        fail(404, "Заявку за цим номером не знайдено.")
    return {"status": order.status, "label": LABELS[order.status]}
