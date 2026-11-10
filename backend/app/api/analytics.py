from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal
from fastapi import APIRouter
from sqlalchemy import func, select
from ..core.security import Admin, Db, fail
from ..models.models import Device, Order, OrderPart, Part, Payment, User, now
from ..services.domain import ACTIVE, LABELS, local_date, stage_started

STALE_DAYS = 3
APPROVAL_WAIT_DAYS = 2

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
    previous = None
    if start and end:
        length = (end - start).days + 1
        prev_start, prev_end = start - timedelta(days=length), start - timedelta(days=1)
        prev_finished = [o for o in all_orders if o.status == "completed" and o.completed_at
                         and prev_start <= local_date(o.completed_at) <= prev_end]
        prev_revenue = sum((o.total_cost for o in prev_finished), Decimal(0))
        prev_cost = sum((costs.get(o.id, 0) for o in prev_finished), Decimal(0))
        previous = {"start": prev_start, "end": prev_end, "revenue": prev_revenue, "parts_cost": prev_cost,
                    "profit": prev_revenue - prev_cost, "completed": len(prev_finished),
                    "average": round(prev_revenue / len(prev_finished), 2) if prev_finished else 0}
    statuses = Counter(order.status for order in intake)
    methods = {"cash": Decimal(0), "card": Decimal(0), "transfer": Decimal(0)}
    finished_ids = [o.id for o in finished]
    if finished_ids:
        for method, amount in db.execute(select(Payment.method, func.sum(Payment.amount))
                                         .where(Payment.order_id.in_(finished_ids)).group_by(Payment.method)):
            methods[method] = amount
    rated = [o for o in finished if o.rating is not None]
    def average_rating(items):
        return round(sum(o.rating for o in items) / len(items), 2) if items else None
    device_categories = dict(db.execute(select(Device.id, Device.device_category)).all())
    return {
        "previous": previous, "completed": len(finished), "attention": attention(db, all_orders),
        "payment_methods": methods,
        "rating": {"average": average_rating(rated), "count": len(rated),
                   "distribution": {str(stars): sum(o.rating == stars for o in rated) for stars in range(5, 0, -1)},
                   "recent": [{"id": o.id, "order_number": o.order_number, "rating": o.rating, "comment": o.rating_comment}
                              for o in sorted(rated, key=lambda o: o.rated_at, reverse=True)[:5]]},
        "revenue": revenue, "parts_cost": cost, "profit": revenue - cost,
        "active": sum(o.status in ACTIVE for o in all_orders),
        "average": round(revenue / len(finished), 2) if finished else 0,
        "daily": [dict(values, date=day) for day, values in sorted(daily.items())],
        "statuses": {LABELS[stage]: statuses[stage] for stage in LABELS},
        "categories": dict(Counter(device_categories[order.device_id] for order in intake)),
        "staff": [
            {"id": master.id, "name": master.full_name, "specialization": master.specialization,
             "active": sum(o.master_id == master.id and o.status in ACTIVE for o in all_orders),
             "completed": sum(o.master_id == master.id for o in finished),
             "revenue": sum(o.total_cost for o in finished if o.master_id == master.id),
             "rating": average_rating([o for o in rated if o.master_id == master.id])}
            for master in db.scalars(select(User).where(User.role == "master").order_by(User.full_name))
        ],
    }

def attention(db, orders):
    """Що потребує реакції адміністратора: застряглі заявки, мовчання клієнта, дефіцит деталей."""
    active = [o for o in orders if o.status in ACTIVE]
    since = stage_started(db, [o.id for o in active])
    today = local_date(now())
    stale, waiting = [], []
    for order in active:
        days = (today - local_date(since.get(order.id, order.created_at))).days
        device = db.get(Device, order.device_id)
        master = db.get(User, order.master_id) if order.master_id else None
        item = {"id": order.id, "order_number": order.order_number, "device": f"{device.brand} {device.model}",
                "status": order.status, "label": LABELS[order.status], "days": days,
                "master": master.full_name if master else None}
        if order.status == "waiting_approval" and order.client_approval_status == "pending":
            if days >= APPROVAL_WAIT_DAYS:
                waiting.append(item)
        elif days >= STALE_DAYS or (order.status == "registered" and not order.master_id):
            stale.append(item)
    low = [{"id": p.id, "name": p.name, "sku": p.sku, "quantity": p.quantity_in_stock, "minimum": p.min_stock_level}
           for p in db.scalars(select(Part).where(Part.quantity_in_stock <= Part.min_stock_level).order_by(Part.quantity_in_stock))]
    by_days = lambda item: -item["days"]
    return {"stale": sorted(stale, key=by_days), "waiting_approval": sorted(waiting, key=by_days), "low_stock": low,
            "stale_days": STALE_DAYS, "approval_days": APPROVAL_WAIT_DAYS}

@router.get("/export.csv")
def export_dashboard(db: Db, user: Admin, start: date | None = None, end: date | None = None):
    """Звіт аналітики за період у CSV для Excel."""
    from .orders import csv_response, money_text
    data = dashboard(db, user, start, end)
    period = f"{start:%d.%m.%Y} – {end:%d.%m.%Y}" if start and end else "увесь час"
    rows = [["Звіт TechDesk", period], [], ["Показник", "Значення"],
            ["Виручка, грн", money_text(data["revenue"])], ["Собівартість запчастин, грн", money_text(data["parts_cost"])],
            ["Розрахунковий прибуток, грн", money_text(data["profit"])], ["Завершено заявок", data["completed"]],
            ["Середній чек, грн", money_text(data["average"])],
            ["Середня оцінка клієнтів", money_text(data["rating"]["average"]) if data["rating"]["average"] else "—"],
            ["Кількість оцінок", data["rating"]["count"]], ["Активні ремонти зараз", data["active"]],
            [], ["Спосіб оплати", "Сума, грн"]]
    rows += [[label, money_text(data["payment_methods"][key])] for key, label in
             (("cash", "Готівка"), ("card", "Картка"), ("transfer", "Переказ"))]
    rows += [[], ["Дата", "Виручка, грн", "Запчастини, грн", "Прибуток, грн"]]
    rows += [[day["date"], money_text(day["revenue"]), money_text(day["parts_cost"]), money_text(day["profit"])] for day in data["daily"]]
    rows += [[], ["Майстер", "Активні", "Завершено", "Виручка, грн", "Оцінка"]]
    rows += [[m["name"], m["active"], m["completed"], money_text(m["revenue"]), money_text(m["rating"]) if m["rating"] else "—"] for m in data["staff"]]
    rows += [[], ["Етап (заявки, прийняті за період)", "Кількість"]] + [[k, v] for k, v in data["statuses"].items()]
    return csv_response(rows, f"techdesk-analytics-{start or 'all'}-{end or 'all'}.csv")
