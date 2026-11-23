import logging
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://techdesk:techdesk@localhost:5432/techdesk")
for prefix in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(prefix):
        DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len(prefix):]
DEMO_MODE = os.getenv("DEMO_MODE", "false").strip().lower() == "true"
JWT_SECRET = (os.getenv("JWT_SECRET") or "").strip()
if not JWT_SECRET:
    if not DEMO_MODE:
        raise RuntimeError("Задайте JWT_SECRET (щонайменше 32 випадкові символи) у .env")
    JWT_SECRET = secrets.token_urlsafe(48)
    logging.getLogger("techdesk").warning("JWT_SECRET не задано: використано тимчасовий ключ, сеанси завершаться після перезапуску")
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET має містити щонайменше 32 символи")
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:5173").rstrip("/")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").strip()
MAIL_FROM = os.getenv("MAIL_FROM", "").strip() or SMTP_USER
