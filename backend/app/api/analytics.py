from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import APIRouter
from sqlalchemy import and_, func, or_, select
from ..core.security import Admin, Db, fail
from ..models.models import Device, Order, OrderPart, Part, Payment, User, now
from ..services.domain import ACTIVE, CLOSED, LABELS, local_date, preload, repair_started, stage_started

STALE_DAYS = 3
APPROVAL_WAIT_DAYS = 2

router = APIRouter(prefix="/api/analytics")
KYIV = ZoneInfo("Europe/Kyiv")

def day_start(day):
    return datetime.combine(day, time(), KYIV)

def period_orders(start, end):
    if not start and not end:
        return select(Order)
    def window(column, low):
        clauses = [column >= day_start(low)] if low else []
        if end:
            clauses.append(column < day_start(end + timedelta(days=1)))
        return and_(*clauses)
    completed_from = start - timedelta(days=(end - start).days + 1) if start and end else start
    return select(Order).where(or_(Order.status.in_(ACTIVE), window(Order.created_at, start),
                                   window(Order.completed_at, completed_from)))

@router.get("/dashboard")
def dashboard(db: Db, user: Admin, start: date | None = None, end: date | None = None):
    if start and end and start > end:
        fail(422, "Дата початку має передувати даті завершення.")
    all_orders = list(db.scalars(period_orders(start, end).order_by(Order.id)))
    def in_period(value):
        day = local_date(value)
        return (not start or day >= start) and (not end or day <= end)
    closed = [o for o in all_orders if o.status in CLOSED and o.completed_at and in_period(o.completed_at)]
    finished = [o for o in closed if o.status == "completed"]
    intake = [o for o in all_orders if in_period(o.created_at)]
    closed_ids = [o.id for o in all_orders if o.status in CLOSED]
    costs = dict(db.execute(select(OrderPart.order_id, func.sum(OrderPart.unit_cost_price * OrderPart.quantity))
                            .where(OrderPart.order_id.in_(closed_ids)).group_by(OrderPart.order_id)).all()) if closed_ids else {}
    def income(order):
        return order.total_cost if order.status == "completed" else order.paid_amount
    def parts_cost(order):
        return costs.get(order.id, 0) if order.status == "completed" or repair_started(order) else 0
    revenue = sum((income(o) for o in closed), Decimal(0))
    cost = sum((parts_cost(o) for o in closed), Decimal(0))
    repairs_revenue = sum((o.total_cost for o in finished), Decimal(0))
    daily = defaultdict(lambda: {"revenue": Decimal(0), "parts_cost": Decimal(0), "profit": Decimal(0)})
    for order in closed:
        day = daily[str(local_date(order.completed_at))]
        day["revenue"] += income(order)
        day["parts_cost"] += parts_cost(order)
        day["profit"] += income(order) - parts_cost(order)
    previous = None
    if start and end:
        length = (end - start).days + 1
        prev_start, prev_end = start - timedelta(days=length), start - timedelta(days=1)
        prev_closed = [o for o in all_orders if o.status in CLOSED and o.completed_at
                       and prev_start <= local_date(o.completed_at) <= prev_end]
        prev_finished = [o for o in prev_closed if o.status == "completed"]
        prev_revenue = sum((income(o) for o in prev_closed), Decimal(0))
        prev_cost = sum((parts_cost(o) for o in prev_closed), Decimal(0))
        previous = {"start": prev_start, "end": prev_end, "revenue": prev_revenue, "parts_cost": prev_cost,
                    "profit": prev_revenue - prev_cost, "completed": len(prev_finished),
                    "average": round(sum((o.total_cost for o in prev_finished), Decimal(0)) / len(prev_finished), 2) if prev_finished else 0}
    statuses = Counter(order.status for order in intake)
    methods = {"cash": Decimal(0), "card": Decimal(0), "transfer": Decimal(0)}
    paid_ids = [o.id for o in closed]
    if paid_ids:
        for method, amount in db.execute(select(Payment.method, func.sum(Payment.amount))
                                         .where(Payment.order_id.in_(paid_ids)).group_by(Payment.method)):
            methods[method] = amount
    rated = [o for o in finished if o.rating is not None]
    def average_rating(items):
        return round(sum(o.rating for o in items) / len(items), 2) if items else None
    intake_devices = {o.device_id for o in intake}
    device_categories = dict(db.execute(select(Device.id, Device.device_category)
                                        .where(Device.id.in_(intake_devices))).all()) if intake_devices else {}
    return {
        "previous": previous, "completed": len(finished), "attention": attention(db, all_orders),
        "payment_methods": methods,
        "rating": {"average": average_rating(rated), "count": len(rated),
                   "distribution": {str(stars): sum(o.rating == stars for o in rated) for stars in range(5, 0, -1)},
                   "recent": [{"id": o.id, "order_number": o.order_number, "rating": o.rating, "comment": o.rating_comment}
                              for o in sorted(rated, key=lambda o: o.rated_at, reverse=True)[:5]]},
        "revenue": revenue, "parts_cost": cost, "profit": revenue - cost,
        "active": sum(o.status in ACTIVE for o in all_orders),
        "average": round(repairs_revenue / len(finished), 2) if finished else 0,
        "daily": [dict(values, date=day) for day, values in sorted(daily.items())],
        "statuses": {LABELS[stage]: statuses[stage] for stage in LABELS},
        "categories": dict(Counter(device_categories[order.device_id] for order in intake)),
        "staff": [
            {"id": master.id, "name": master.full_name, "specialization": master.specialization,
             "active": sum(o.master_id == master.id and o.status in ACTIVE for o in all_orders),
             "completed": sum(o.master_id == master.id for o in finished),
             "revenue": sum(income(o) for o in closed if o.master_id == master.id),
             "rating": average_rating([o for o in rated if o.master_id == master.id])}
            for master in db.scalars(select(User).where(User.role == "master").order_by(User.full_name))
        ],
    }

def attention(db, orders):
    active = [o for o in orders if o.status in ACTIVE]
    since = stage_started(db, [o.id for o in active])
    devices, people = preload(db, active)
    today = local_date(now())
    stale, waiting = [], []
    for order in active:
        days = (today - local_date(since.get(order.id, order.created_at))).days
        device = devices[order.device_id]
        master = people.get(order.master_id)
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

@router.get("/export.xlsx")
def export_dashboard_xlsx(db: Db, user: Admin, start: date | None = None, end: date | None = None):
    from decimal import Decimal
    from ..services.excel import report_sheet, xlsx_response
    data = dashboard(db, user, start, end)
    period = f"{start:%d.%m.%Y} – {end:%d.%m.%Y}" if start and end else "увесь час"
    money = lambda v: Decimal(v or 0)
    sections = [
        ("Підсумки", ["Показник", "Значення"], [
            ["Виручка, грн", money(data["revenue"])], ["Собівартість запчастин, грн", money(data["parts_cost"])],
            ["Розрахунковий прибуток, грн", money(data["profit"])], ["Завершено заявок", data["completed"]],
            ["Середній чек, грн", money(data["average"])],
            ["Середня оцінка клієнтів", round(float(data["rating"]["average"]), 2) if data["rating"]["average"] else "—"],
            ["Кількість оцінок", data["rating"]["count"]], ["Активні ремонти зараз", data["active"]]]),
        ("Оплати за способом", ["Спосіб оплати", "Сума, грн"],
         [[label, money(data["payment_methods"][key])] for key, label in
          (("cash", "Готівка"), ("card", "Картка"), ("transfer", "Переказ"))]),
        ("По днях", ["Дата", "Виручка, грн", "Запчастини, грн", "Прибуток, грн"],
         [[date.fromisoformat(day["date"]), money(day["revenue"]), money(day["parts_cost"]), money(day["profit"])] for day in data["daily"]]),
        ("Майстри", ["Майстер", "Активні", "Завершено", "Виручка, грн", "Оцінка"],
         [[m["name"], m["active"], m["completed"], money(m["revenue"]), round(float(m["rating"]), 2) if m["rating"] else "—"]
          for m in data["staff"]]),
        ("Етапи заявок, прийнятих за період", ["Етап", "Кількість"], [[k, v] for k, v in data["statuses"].items()]),
    ]
    return xlsx_response(lambda wb: report_sheet(wb, "Аналітика", f"Звіт TechDesk · {period}", sections),
                         f"techdesk-analytics-{start or 'all'}-{end or 'all'}.xlsx")
