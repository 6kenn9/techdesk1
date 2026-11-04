import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://techdesk:techdesk@localhost:5432/techdesk")
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
JWT_SECRET = os.getenv("JWT_SECRET") or ("techdesk-local-demo-key-change-me-32-chars" if DEMO_MODE else "")
if len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET має містити щонайменше 32 символи")
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:5173").rstrip("/")
