import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from db.models import Rule, Mitigation, RuleAuditLog
from api.schemas.rules import RuleCreate, RuleUpdate, TransitionRequest, TestRuleRequest
from engine.cache import rule_cache
from engine.evaluator import EVALUATORS

router = APIRouter(prefix="/admin")

VALID_TRANSITIONS = {
    "draft":        ["under_review", "deactivated"],
    "under_review": ["activated", "draft"],
    "activated":    ["deactivated"],
    "deactivated":  [],
}


@router.get("/rules")
def list_all_rules(db: Session = Depends(get_db)):
    rules = db.query(Rule).order_by(Rule.slug, Rule.created_at.desc()).all()
    return [_fmt(r) for r in rules]


@router.post("/rules", status_code=201)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db)):
    rule = Rule(
        slug=payload.slug,
        category=payload.category,
        name=payload.name,
        written_rule=payload.written_rule,
        type=payload.type,
        definition=json.dumps(payload.definition),
        status="draft",
        author_id=payload.author_id,
        author_name=payload.author_name,
        change_note=payload.change_note,
    )
    db.add(rule)
    db.flush()
    _replace_mitigations(db, rule.id, payload.mitigations)
    db.add(RuleAuditLog(
        rule_id=rule.id,
        from_status=None,
        to_status="draft",
        author_id=payload.author_id,
        author_name=payload.author_name,
        note="Rule created",
    ))
    db.commit()
    db.refresh(rule)
    return _fmt(rule)


@router.get("/rules/{rule_id}")
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _fmt(rule)


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, payload: RuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if rule.status != "draft":
        raise HTTPException(status_code=422, detail="Only draft rules can be updated in place")

    if payload.name is not None:
        rule.name = payload.name
    if payload.written_rule is not None:
        rule.written_rule = payload.written_rule
    if payload.definition is not None:
        rule.definition = json.dumps(payload.definition)
    rule.author_id = payload.author_id
    rule.author_name = payload.author_name
    rule.change_note = payload.change_note

    if payload.mitigations is not None:
        _replace_mitigations(db, rule.id, payload.mitigations)

    db.commit()
    db.refresh(rule)
    return _fmt(rule)


@router.post("/rules/{rule_id}/transition")
def transition_rule(rule_id: int, payload: TransitionRequest, db: Session = Depends(get_db)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    valid = VALID_TRANSITIONS.get(rule.status, [])
    if payload.to_status not in valid:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition '{rule.status}' → '{payload.to_status}'. Valid: {valid}",
        )

    from_status = rule.status
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if payload.to_status == "activated":
        # Atomically deactivate any currently active version of this slug
        existing = db.query(Rule).filter(
            Rule.slug == rule.slug,
            Rule.status == "activated",
            Rule.id != rule.id,
        ).all()
        for old in existing:
            old.status = "deactivated"
            old.deactivated_at = now
            db.add(RuleAuditLog(
                rule_id=old.id,
                from_status="activated",
                to_status="deactivated",
                author_id=payload.author_id,
                author_name=payload.author_name,
                note=f"Superseded by rule version {rule.id}",
            ))
        rule.activated_at = now

    if payload.to_status == "deactivated":
        rule.deactivated_at = now

    rule.status = payload.to_status
    db.add(RuleAuditLog(
        rule_id=rule.id,
        from_status=from_status,
        to_status=payload.to_status,
        author_id=payload.author_id,
        author_name=payload.author_name,
        note=payload.note,
    ))
    db.commit()

    if payload.to_status in ("activated", "deactivated") or from_status == "activated":
        rule_cache.invalidate()

    return _fmt(rule)


@router.post("/rules/{rule_id}/test")
def test_rule(rule_id: int, request: TestRuleRequest, db: Session = Depends(get_db)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    if rule.status not in ("draft", "under_review"):
        raise HTTPException(status_code=422, detail="Only draft or under_review rules can be tested")

    evaluator_class = EVALUATORS.get(rule.type)
    if evaluator_class is None:
        raise HTTPException(status_code=422, detail=f"Unknown evaluator type: {rule.type}")

    definition = json.loads(rule.definition)
    passes = evaluator_class().evaluate(definition, request.observations)

    return {
        "rule_id": rule.id,
        "rule_slug": rule.slug,
        "rule_name": rule.name,
        "passes": passes,
        "vulnerability_triggered": not passes,
    }


@router.get("/rules/slug/{slug}/history")
def get_rule_history(slug: str, db: Session = Depends(get_db)):
    rules = db.query(Rule).filter(Rule.slug == slug).order_by(Rule.created_at.desc()).all()
    return [_fmt(r) for r in rules]


@router.get("/rules/{rule_id}/audit")
def get_rule_audit(rule_id: int, db: Session = Depends(get_db)):
    logs = (
        db.query(RuleAuditLog)
        .filter(RuleAuditLog.rule_id == rule_id)
        .order_by(RuleAuditLog.created_at.desc())
        .all()
    )
    return [
        {
            "from_status": log.from_status,
            "to_status": log.to_status,
            "author_id": log.author_id,
            "author_name": log.author_name,
            "note": log.note,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


def _replace_mitigations(db, rule_id: int, mitigations):
    db.query(Mitigation).filter(Mitigation.rule_id == rule_id).delete()
    for m in mitigations:
        db.add(Mitigation(
            rule_id=rule_id,
            type=m.type,
            name=m.name,
            description=m.description,
            modifier_params=json.dumps(m.modifier_params) if m.modifier_params else None,
        ))


def _fmt(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "slug": rule.slug,
        "category": rule.category,
        "name": rule.name,
        "written_rule": rule.written_rule,
        "type": rule.type,
        "definition": json.loads(rule.definition),
        "status": rule.status,
        "activated_at": rule.activated_at.isoformat() if rule.activated_at else None,
        "deactivated_at": rule.deactivated_at.isoformat() if rule.deactivated_at else None,
        "author_id": rule.author_id,
        "author_name": rule.author_name,
        "change_note": rule.change_note,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "mitigations": [
            {
                "id": m.id,
                "type": m.type,
                "name": m.name,
                "description": m.description,
                "modifier_params": json.loads(m.modifier_params) if m.modifier_params else None,
            }
            for m in rule.mitigations
        ],
    }
