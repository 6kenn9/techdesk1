from getpass import getpass
from pydantic import ValidationError
from app.api.auth import create_account
from app.core.database import SessionLocal
from app.schemas.schemas import Registration

if __name__ == "__main__":
    try:
        account = Registration(full_name=input("Ім’я та прізвище: "), email=input("Електронна пошта: "),
                               phone=input("Телефон: "), password=getpass("Пароль: "))
    except ValidationError:
        raise SystemExit("Перевірте формат пошти, телефону й довжину пароля (від 8 символів).")
    with SessionLocal() as session:
        create_account(session, account, "admin")
    print("Адміністратора створено.")
