import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from .api import analytics, auth, inbox, intake, orders, passports, pdf_generator, warehouse
from .core.config import DEMO_MODE, TELEGRAM_BOT_TOKEN, TELEGRAM_BOT_USERNAME
from .core.database import SessionLocal
from .core.security import Db, RateLimiter, fail, throttle
from .models.models import Device, Order
from .services.domain import LABELS

# Повідомлення програми (зокрема про запуск Telegram-бота) видно в docker compose logs backend.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(app):
    if DEMO_MODE:
        from .services.seed_service import seed
        with SessionLocal() as session:
            seed(session)
    from .services import telegram
    if TELEGRAM_BOT_TOKEN and not telegram.bot:
        try:
            candidate = telegram.Bot(telegram.TelegramApi(TELEGRAM_BOT_TOKEN), TELEGRAM_BOT_USERNAME)
            candidate.start()
            telegram.bot = candidate
            logging.getLogger("techdesk.telegram").info("Telegram-бот @%s запущено", candidate.username)
        except Exception as error:
            logging.getLogger("techdesk.telegram").warning("Telegram-бот не запущено: %s", error)
    yield
    if telegram.bot and telegram.bot.background:
        telegram.bot.stop()

app = FastAPI(title="TechDesk — API сервісного центру", version="1.0.0", lifespan=lifespan)
for module in (intake, inbox, auth, passports, orders, warehouse, analytics, pdf_generator):
    app.include_router(module.router)
app.include_router(passports.photos)

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

tracking = RateLimiter(limit=30, window=60)

@app.get("/api/track", dependencies=[throttle(tracking, "track")])
def track(code: str, db: Db):
    value = code.strip().upper()
    if not 2 <= len(value) <= 80:
        fail(422, "Введіть номер заявки або серійний номер.")
    order = db.scalar(select(Order).join(Device, Device.id == Order.device_id).where(
        or_(Order.order_number == value, Device.serial_number == value)).order_by(Order.id.desc()).limit(1))
    if not order:
        fail(404, "Заявку за цим номером не знайдено.")
    return {"status": order.status, "label": LABELS[order.status]}
