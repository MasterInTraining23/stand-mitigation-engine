from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Rule
from db.queries import query_active_rules, query_active_rules_at

router = APIRouter()


@router.get("/rules")
def list_rules(as_of: Optional[datetime] = None, db: Session = Depends(get_db)):
    rules = query_active_rules_at(db, as_of) if as_of else query_active_rules(db)
    return [_format_rule(r) for r in rules]


@router.get("/rules/{slug}/mitigations")
def get_rule_mitigations(slug: str, db: Session = Depends(get_db)):
    rule = db.query(Rule).filter(Rule.slug == slug, Rule.status == "activated").first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return [
        {"type": m.type, "name": m.name, "description": m.description}
        for m in rule.mitigations
    ]


def _format_rule(rule: Rule):
    return {
        "slug": rule.slug,
        "category": rule.category,
        "name": rule.name,
        "written_rule": rule.written_rule,
        "type": rule.type,
        "mitigations": [
            {"type": m.type, "name": m.name, "description": m.description}
            for m in rule.mitigations
        ],
    }
