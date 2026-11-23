from sqlalchemy import event
from sqlalchemy.orm import Session

def emit(db, kind, order_id):
    from . import telegram
    if telegram.bot:
        db.info.setdefault("telegram_events", []).append((kind, order_id))

@event.listens_for(Session, "after_commit")
def _deliver(session):
    events = session.info.pop("telegram_events", None)
    if events:
        from . import telegram
        if telegram.bot:
            telegram.bot.submit(events)

@event.listens_for(Session, "after_rollback")
def _discard(session):
    session.info.pop("telegram_events", None)
