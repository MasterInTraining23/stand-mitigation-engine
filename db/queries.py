from sqlalchemy import or_
from sqlalchemy.orm import Session
from .models import Rule


def query_active_rules(db: Session):
    return db.query(Rule).filter(Rule.status == "activated").all()


def query_active_rules_at(db: Session, as_of_ms: int):
    return db.query(Rule).filter(
        Rule.activated_at <= as_of_ms,
        or_(Rule.deactivated_at == None, Rule.deactivated_at > as_of_ms),
    ).all()


def query_active_rules_in_range(db: Session, from_ms: int, to_ms: int):
    """Returns rules active at any point during [from_ms, to_ms] (epoch milliseconds).

    Standard overlapping intervals check:
      activated_at <= to_ms  AND  (deactivated_at IS NULL OR deactivated_at > from_ms)
    """
    return db.query(Rule).filter(
        Rule.activated_at != None,
        Rule.activated_at <= to_ms,
        or_(Rule.deactivated_at == None, Rule.deactivated_at > from_ms),
    ).all()
