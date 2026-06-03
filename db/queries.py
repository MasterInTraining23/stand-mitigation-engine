from datetime import datetime
from sqlalchemy.orm import Session
from .models import Rule


def query_active_rules(db: Session):
    return db.query(Rule).filter(Rule.status == "activated").all()


def query_active_rules_at(db: Session, as_of: datetime):
    # Strip timezone for SQLite naive datetime comparison
    if as_of.tzinfo is not None:
        from datetime import timezone
        as_of = as_of.astimezone(timezone.utc).replace(tzinfo=None)
    return db.query(Rule).filter(
        Rule.activated_at <= as_of,
        (Rule.deactivated_at == None) | (Rule.deactivated_at > as_of),
    ).all()
