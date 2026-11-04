from fastapi import APIRouter
from sqlalchemy import select
from ..core.security import Admin, Db, Staff, fail
from ..models.models import Movement, Part, Service, User
from ..schemas.schemas import PartCreate, PartInput, Quantity, ServiceInput
from ..services.domain import lock_part, row, stock_move

router = APIRouter(prefix="/api/warehouse")

@router.get("/parts")
def list_parts(db: Db, user: Staff, q: str = "", category: str = "", low: bool = False):
    query = select(Part).order_by(Part.name)
    if q:
        query = query.where(Part.name.icontains(q, autoescape=True) | Part.sku.icontains(q, autoescape=True))
    if category:
        query = query.where(Part.category == category)
    if low:
        query = query.where(Part.quantity_in_stock <= Part.min_stock_level)
    return [row(part, *(() if user.role == "admin" else ("cost_price",))) for part in db.scalars(query)]

@router.post("/parts", status_code=201)
def create_part(payload: PartCreate, db: Db, user: Admin):
    part = Part(**payload.model_dump(exclude={"quantity_in_stock"}))
    db.add(part)
    db.flush()
    if payload.quantity_in_stock:
        stock_move(db, part, payload.quantity_in_stock, user.id, "Початковий залишок")
    db.commit()
    return row(part)

@router.patch("/parts/{part_id}")
def edit_part(part_id: int, payload: PartInput, db: Db, user: Admin):
    part = lock_part(db, part_id)
    for key, value in payload.model_dump().items():
        setattr(part, key, value)
    db.commit()
    return row(part)

@router.post("/parts/{part_id}/restock")
def restock(part_id: int, payload: Quantity, db: Db, user: Admin):
    part = lock_part(db, part_id)
    stock_move(db, part, payload.quantity, user.id, "Оприбуткування на склад")
    db.commit()
    return row(part)

@router.get("/services")
def services(db: Db, user: Staff):
    return [row(service) for service in db.scalars(select(Service).order_by(Service.name))]

@router.post("/services", status_code=201)
def create_service(payload: ServiceInput, db: Db, user: Admin):
    service = Service(**payload.model_dump())
    db.add(service)
    db.commit()
    return row(service)

@router.put("/services/{service_id}")
def edit_service(service_id: int, payload: ServiceInput, db: Db, user: Admin):
    service = db.get(Service, service_id)
    if not service:
        fail(404, "Послугу не знайдено.")
    for key, value in payload.model_dump().items():
        setattr(service, key, value)
    db.commit()
    return row(service)

@router.get("/transactions")
def transactions(db: Db, user: Admin):
    return [dict(row(item), part_name=db.get(Part, item.part_id).name, user_name=db.get(User, item.user_id).full_name)
            for item in db.scalars(select(Movement).order_by(Movement.id.desc()).limit(100))]
