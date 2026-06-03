from datetime import datetime, timezone
from sqlalchemy import or_
from sqlalchemy.orm import Session
from .models import Rule


def query_active_rules(db: Session):
    return db.query(Rule).filter(Rule.status == "activated").all()


def query_active_rules_at(db: Session, as_of: datetime):
    as_of = _to_naive_utc(as_of)
    return db.query(Rule).filter(
        Rule.activated_at <= as_of,
        or_(Rule.deactivated_at == None, Rule.deactivated_at > as_of),
    ).all()


def query_active_rules_in_range(db: Session, from_date: datetime, to_date: datetime):
    """Returns rules active at any point during [from_date, to_date].

    Uses the standard overlapping intervals check:
      activated_at <= to_date  AND  (deactivated_at IS NULL OR deactivated_at > from_date)
    """
    from_date = _to_naive_utc(from_date)
    to_date = _to_naive_utc(to_date)
    return db.query(Rule).filter(
        Rule.activated_at != None,
        Rule.activated_at <= to_date,
        or_(Rule.deactivated_at == None, Rule.deactivated_at > from_date),
    ).all()


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
