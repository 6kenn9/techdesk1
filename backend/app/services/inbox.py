"""Сповіщення працівників на сайті: про нові заявки клієнтів, рішення щодо кошторису й скасування."""
from sqlalchemy import select
from ..models.models import Device, Notification, User

def notify_staff(db, order, kind, text, actor_id):
    """Отримувачі: адміністратори та відповідальний майстер; для нової вільної заявки — усі активні майстри."""
    staff = db.scalars(select(User).where(User.is_active.is_(True), User.role.in_(("admin", "master"))))
    recipients = set()
    for person in staff:
        if person.role == "admin" or person.id == order.master_id or (order.master_id is None and kind in ("new", "cancelled")):
            recipients.add(person.id)
    recipients.discard(actor_id)
    for user_id in sorted(recipients):
        db.add(Notification(user_id=user_id, order_id=order.id, kind=kind, text=text[:300]))

def describe(db, order):
    device = db.get(Device, order.device_id)
    client = db.get(User, order.client_id)
    return f"{order.order_number} · {device.brand} {device.model} · {client.full_name}"
