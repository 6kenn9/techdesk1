"""Сповіщення працівників на сайті."""
from fastapi import APIRouter
from sqlalchemy import func, select, update
from ..core.security import Db, Staff
from ..models.models import Notification, Order, now
from ..schemas.schemas import ReadNotifications

router = APIRouter(prefix="/api/notifications")

@router.get("")
def inbox(db: Db, user: Staff):
    items = db.scalars(select(Notification).where(Notification.user_id == user.id)
                       .order_by(Notification.created_at.desc(), Notification.id.desc()).limit(30)).all()
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.read_at.is_(None)))
    numbers = dict(db.execute(select(Order.id, Order.order_number).where(
        Order.id.in_({item.order_id for item in items if item.order_id}))).all())
    return {"unread": unread, "items": [
        {"id": item.id, "kind": item.kind, "text": item.text, "order_id": item.order_id,
         "order_number": numbers.get(item.order_id), "created_at": item.created_at, "read": item.read_at is not None}
        for item in items]}

@router.post("/read")
def mark_read(payload: ReadNotifications, db: Db, user: Staff):
    query = update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))
    if payload.ids:
        query = query.where(Notification.id.in_(payload.ids))
    db.execute(query.values(read_at=now()))
    db.commit()
    return {"ok": True}
