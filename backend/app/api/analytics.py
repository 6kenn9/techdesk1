from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from fastapi import APIRouter
from sqlalchemy import func, select
from ..core.security import Admin, Db, fail
from ..models.models import Device, Order, OrderPart, User
from ..services.domain import ACTIVE, LABELS, local_date

router = APIRouter(prefix="/api/analytics")

@router.get("/dashboard")
def dashboard(db: Db, user: Admin, start: date | None = None, end: date | None = None):
    if start and end and start > end:
        fail(422, "Дата початку має передувати даті завершення.")
    all_orders = list(db.scalars(select(Order).order_by(Order.id)))
    def in_period(value):
        day = local_date(value)
        return (not start or day >= start) and (not end or day <= end)
    finished = [o for o in all_orders if o.status == "completed" and o.completed_at and in_period(o.completed_at)]
    intake = [o for o in all_orders if in_period(o.created_at)]
    costs = dict(db.execute(select(OrderPart.order_id, func.sum(OrderPart.unit_cost_price * OrderPart.quantity))
                            .group_by(OrderPart.order_id)).all())
    revenue = sum((o.total_cost for o in finished), Decimal(0))
    cost = sum((costs.get(o.id, 0) for o in finished), Decimal(0))
    daily = defaultdict(lambda: {"revenue": Decimal(0), "parts_cost": Decimal(0), "profit": Decimal(0)})
    for order in finished:
        day = daily[str(local_date(order.completed_at))]
        part_cost = costs.get(order.id, 0)
        day["revenue"] += order.total_cost
        day["parts_cost"] += part_cost
        day["profit"] += order.total_cost - part_cost
    statuses = Counter(order.status for order in intake)
    return {
        "revenue": revenue, "parts_cost": cost, "profit": revenue - cost,
        "active": sum(o.status in ACTIVE for o in all_orders),
        "average": round(revenue / len(finished), 2) if finished else 0,
        "daily": [dict(values, date=day) for day, values in sorted(daily.items())],
        "statuses": {LABELS[stage]: statuses[stage] for stage in LABELS},
        "categories": dict(Counter(db.get(Device, order.device_id).device_category for order in intake)),
        "staff": [
            {"id": master.id, "name": master.full_name, "specialization": master.specialization,
             "active": sum(o.master_id == master.id and o.status in ACTIVE for o in all_orders),
             "completed": sum(o.master_id == master.id for o in finished),
             "revenue": sum(o.total_cost for o in finished if o.master_id == master.id)}
            for master in db.scalars(select(User).where(User.role == "master").order_by(User.full_name))
        ],
    }
