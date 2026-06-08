import json
import shutil
import subprocess
from fastapi import APIRouter

router = APIRouter()

EXTRACT_OBSERVATIONS_PROMPT = """You are extracting property observations for a wildfire risk assessment form.

Supported observation fields (extract ONLY fields explicitly mentioned):
- attic_vent_screens: one of "None", "Standard", "Ember Resistant"
- roof_type: one of "Class A", "Class B", "Class C"
- window_type: one of "Single", "Double", "Tempered Glass"
- wildfire_risk_category: one of "A", "B", "C", "D"
- home_to_home_distance: number in feet (distance to nearest neighboring structure)
- vegetation: array of objects, each with:
    - type: "Tree", "Shrub", or "Grass"
    - distance_to_window: number in feet

Return a JSON object with exactly two keys:
- "observations": object containing only the supported fields you could confidently extract
- "unsupported": array of short strings describing any observations or details in the text that could not be mapped to the supported fields above (e.g., "garage door material", "foundation type")

Return only valid JSON, no markdown, no explanation.

Inspection text:
"""

EXTRACT_RULE_PROMPT = """You are building a wildfire mitigation rule definition for a rules engine.

The engine supports exactly two rule types:

1. boolean_condition — checks if an observation matches a condition.
   Definition: {"condition": <node>}
   Node operators:
     {"eq":  [operand, value]}       — equality
     {"in":  [operand, list]}        — membership
     {"gte": [operand, number]}      — >=
     {"lte": [operand, number]}      — <=
     {"and": [node, node, ...]}      — all must pass
     {"or":  [node, node, ...]}      — any must pass
     {"not": node}                   — negation
   For observation fields use: {"field": "field_name"}

2. threshold_condition — checks distance/measurement thresholds for list items (e.g. vegetation distances).
   Definition: {
     "base_value": number,
     "subject_field": "field_name",           // list field in observations (e.g. "vegetation")
     "measurement_field": "field_name",        // numeric field on each item (e.g. "distance_to_window")
     "modifiers": {                            // optional: adjust threshold based on field values
       "field_name": {
         "value_name": {"op": "multiply"|"divide"|"add"|"subtract", "value": number}
       }
     }
   }

Known observation fields: attic_vent_screens, roof_type, window_type, wildfire_risk_category, home_to_home_distance, vegetation

Return a JSON object with exactly two keys:
- "rule": object with fields:
    - slug: snake_case unique identifier
    - category: short lowercase category (e.g. "roof", "site", "windows")
    - name: concise human-readable rule name
    - written_rule: full policy text written for policyholders (1-3 sentences)
    - type: "boolean_condition" or "threshold_condition"
    - definition: the rule definition JSON per schema above
- "unsupported": array of short strings describing rule aspects that could NOT be expressed in the supported schema

Return only valid JSON, no markdown, no explanation.

Rule description:
"""


def _run_claude(prompt: str) -> dict:
    result = subprocess.run(
        ['claude', '-p', '--model', 'sonnet'],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=45,
    )
    raw = result.stdout.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        inner = lines[1:] if len(lines) > 1 else lines
        raw = "\n".join(inner[:-1] if inner and inner[-1].strip() == "```" else inner)
    return json.loads(raw.strip())


@router.get("/ai/available")
def ai_available():
    return {"available": shutil.which("claude") is not None}


@router.post("/ai/extract-observations")
async def extract_observations(payload: dict):
    text = payload.get("text", "").strip()
    if not text:
        return {"observations": {}, "unsupported": []}
    try:
        return _run_claude(EXTRACT_OBSERVATIONS_PROMPT + text)
    except Exception as e:
        return {"observations": {}, "unsupported": [], "error": str(e)}


@router.post("/ai/extract-rule")
async def extract_rule(payload: dict):
    text = payload.get("text", "").strip()
    if not text:
        return {"rule": {}, "unsupported": []}
    try:
        return _run_claude(EXTRACT_RULE_PROMPT + text)
    except Exception as e:
        return {"rule": {}, "unsupported": [], "error": str(e)}
