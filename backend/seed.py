from app.core.database import SessionLocal
from app.services.seed_service import seed

if __name__ == "__main__":
    with SessionLocal() as session:
        print("Демонстраційні дані додано." if seed(session) else "База вже містить користувачів.")
