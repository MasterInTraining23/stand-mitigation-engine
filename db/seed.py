import json
from datetime import datetime, timezone
from .database import SessionLocal
from .models import Rule, Mitigation, RuleAuditLog

SEED_RULES = [
    {
        "slug": "attic_vent_screens",
        "category": "attic",
        "name": "Attic Vent — Ember Resistance",
        "written_rule": "Ensure all vents, chimneys, and screens can withstand embers (i.e., should be ember-rated).",
        "type": "boolean_condition",
        "definition": {
            "condition": {
                "eq": [{"field": "attic_vent_screens"}, "Ember Resistant"]
            }
        },
        "mitigations": [
            {
                "type": "full",
                "name": "Install Ember-Resistant Vents",
                "description": "Replace existing vents with ember-rated vent covers on all attic openings.",
            },
        ],
    },
    {
        "slug": "roof_class",
        "category": "roof",
        "name": "Roof — Class Rating",
        "written_rule": (
            "Ensure the roof is Class A by assembly, free of gaps, and well maintained. "
            "In low wildfire areas (Category A) roofs can be Class B or Class A."
        ),
        "type": "boolean_condition",
        "definition": {
            "condition": {
                "or": [
                    {"eq": [{"field": "roof_type"}, "Class A"]},
                    {
                        "and": [
                            {"eq": [{"field": "wildfire_risk_category"}, "A"]},
                            {"in": [{"field": "roof_type"}, ["Class A", "Class B"]]},
                        ]
                    },
                ]
            }
        },
        "mitigations": [
            {
                "type": "full",
                "name": "Replace Roof with Class A Assembly",
                "description": "Upgrade the existing roof to a Class A fire-rated assembly, ensuring no gaps and proper maintenance.",
            },
        ],
    },
    {
        "slug": "home_to_home_distance",
        "category": "site",
        "name": "Home-to-Home Distance",
        "written_rule": (
            "Neighboring homes must be at least 15 feet away. Distance is measured as the "
            "minimum edge-to-edge Euclidean distance between building footprints."
        ),
        "type": "boolean_condition",
        "definition": {
            "condition": {
                "gte": [{"field": "home_to_home_distance"}, 15.0]
            }
        },
        "mitigations": [],
    },
    {
        "slug": "windows_vegetation_distance",
        "category": "windows",
        "name": "Windows — Vegetation Distance",
        "written_rule": (
            "Ensure windows can withstand heat exposure of surrounding combustibles and vegetation burning. "
            "Safe distance is calculated from a 30ft base for tempered glass from trees, "
            "adjusted by window type and vegetation type."
        ),
        "type": "threshold_condition",
        "definition": {
            "base_value": 30,
            "subject_field": "vegetation",
            "measurement_field": "distance_to_window",
            "modifiers": {
                "window_type": {
                    "Single":         {"op": "multiply", "value": 3},
                    "Double":         {"op": "multiply", "value": 2},
                    "Tempered Glass": {"op": "multiply", "value": 1},
                },
                "type": {
                    "Tree":  {"op": "multiply", "value": 1},
                    "Shrub": {"op": "divide",   "value": 2},
                    "Grass": {"op": "divide",   "value": 3},
                },
            },
        },
        "mitigations": [
            {
                "type": "full",
                "name": "Remove Vegetation",
                "description": "Remove all trees, shrubs, and grass within the calculated safe distance from windows.",
            },
            {
                "type": "full",
                "name": "Replace Windows with Tempered Glass",
                "description": "Upgrade all windows to tempered glass to reduce the required safe distance.",
            },
            {
                "type": "bridge",
                "name": "Apply Window Film",
                "description": "Apply fire-resistant film to windows, decreasing minimum safe distance by 20%.",
                "modifier_params": {"factor": 0.8},
            },
            {
                "type": "bridge",
                "name": "Apply Flame Retardant to Shrubs",
                "description": "Treat shrubs with flame retardant, decreasing minimum safe distance by 25%.",
                "modifier_params": {"factor": 0.75},
            },
            {
                "type": "bridge",
                "name": "Prune Trees to Safe Height",
                "description": "Prune trees to a safe height, decreasing minimum safe distance by 50%.",
                "modifier_params": {"factor": 0.5},
            },
        ],
    },
]


def seed_rules():
    db = SessionLocal()
    try:
        from .models import Rule as RuleModel
        if db.query(RuleModel).count() > 0:
            return

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        for rule_data in SEED_RULES:
            rule = Rule(
                slug=rule_data["slug"],
                category=rule_data["category"],
                name=rule_data["name"],
                written_rule=rule_data["written_rule"],
                type=rule_data["type"],
                definition=json.dumps(rule_data["definition"]),
                status="activated",
                activated_at=now,
                author_id="seed",
                author_name="System Seed",
                change_note="Initial seed from spec examples",
            )
            db.add(rule)
            db.flush()

            for m_data in rule_data.get("mitigations", []):
                db.add(Mitigation(
                    rule_id=rule.id,
                    type=m_data["type"],
                    name=m_data["name"],
                    description=m_data.get("description"),
                    modifier_params=json.dumps(m_data["modifier_params"]) if "modifier_params" in m_data else None,
                ))

            db.add(RuleAuditLog(
                rule_id=rule.id,
                from_status=None,
                to_status="activated",
                author_id="seed",
                author_name="System Seed",
                note="Initial activation from spec examples",
            ))

        db.commit()
    finally:
        db.close()
