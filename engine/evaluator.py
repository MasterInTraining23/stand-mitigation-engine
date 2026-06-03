import json
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from .cache import rule_cache
from .evaluators.boolean_condition import BooleanConditionEvaluator
from .evaluators.threshold_condition import ThresholdConditionEvaluator

EVALUATORS = {
    "boolean_condition":  BooleanConditionEvaluator,
    "threshold_condition": ThresholdConditionEvaluator,
}


def evaluate_property(
    observations: dict,
    db: Session,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
):
    rules = rule_cache.get_active_rules(db, from_date=from_date, to_date=to_date)
    vulnerabilities = []

    for rule in rules:
        evaluator_class = EVALUATORS.get(rule.type)
        if evaluator_class is None:
            continue

        definition = json.loads(rule.definition)
        passes, details = evaluator_class().evaluate(definition, observations)

        if not passes:
            vulnerabilities.append({
                "rule_id": rule.id,
                "rule_slug": rule.slug,
                "rule_name": rule.name,
                "category": rule.category,
                "written_rule": rule.written_rule,
                "violation_details": details,
                "full_mitigations": [
                    {"name": m.name, "description": m.description}
                    for m in rule.mitigations if m.type == "full"
                ],
                "bridge_mitigations": [
                    {
                        "name": m.name,
                        "description": m.description,
                        "modifier_params": json.loads(m.modifier_params) if m.modifier_params else None,
                    }
                    for m in rule.mitigations if m.type == "bridge"
                ],
            })

    unmitigatable = [
        v for v in vulnerabilities
        if not v["full_mitigations"] and not v["bridge_mitigations"]
    ]
    bridge_only = [
        v for v in vulnerabilities
        if not v["full_mitigations"] and v["bridge_mitigations"]
    ]

    return {
        "from_date": from_date.strftime("%Y-%m-%dT%H:%M:%SZ") if from_date else None,
        "to_date": to_date.strftime("%Y-%m-%dT%H:%M:%SZ") if to_date else None,
        "evaluated_at": datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "vulnerabilities": vulnerabilities,
        "summary": {
            "total_vulnerabilities": len(vulnerabilities),
            "unmitigatable_count": len(unmitigatable),
            "bridge_mitigation_count": len(bridge_only),
            "categories_affected": list({v["category"] for v in vulnerabilities}),
        },
    }
