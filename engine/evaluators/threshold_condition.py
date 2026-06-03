from .base import BaseEvaluator

OPERATIONS = {
    "multiply": lambda a, b: a * b,
    "divide":   lambda a, b: a / b,
    "add":      lambda a, b: a + b,
    "subtract": lambda a, b: a - b,
}


class ThresholdConditionEvaluator(BaseEvaluator):
    def evaluate(self, definition: dict, observations: dict) -> tuple[bool, list]:
        """
        Returns (passes, item_results).
        item_results contains every subject item with its threshold and pass/fail status,
        including any bridge mitigations applied via observations["applied_mitigations"].
        Returns (True, []) when subject_field is absent or empty.
        """
        subject_field = definition["subject_field"]
        measurement_field = definition["measurement_field"]
        base_value = float(definition["base_value"])
        modifiers = definition.get("modifiers", {})
        mit_modifiers = definition.get("mitigation_modifiers", {})
        applied = set(observations.get("applied_mitigations") or [])

        items = observations.get(subject_field) or []
        if not items:
            return (True, [])

        item_results = []
        all_pass = True

        for item in items:
            threshold = self._compute_threshold(base_value, modifiers, observations, item)
            threshold = self._apply_mitigations(threshold, mit_modifiers, applied, item)
            actual = float(item.get(measurement_field, 0))
            passes = actual >= threshold

            if not passes:
                all_pass = False

            item_results.append({
                "vegetation_type": item.get("type"),
                "actual_distance": actual,
                "required_distance": round(threshold, 1),
                "passes": passes,
            })

        return (all_pass, item_results)

    def _compute_threshold(self, base: float, modifiers: dict, observations: dict, item: dict) -> float:
        threshold = base
        for field, value_map in modifiers.items():
            # Top-level observation fields take precedence over item fields.
            # Known limitation: avoid reusing field names across scopes.
            value = observations.get(field) if observations.get(field) is not None else item.get(field)
            if value is not None and value in value_map:
                op_config = value_map[value]
                op = OPERATIONS.get(op_config["op"])
                if op is None:
                    raise ValueError(f"Unknown operation: {op_config['op']}")
                threshold = op(threshold, float(op_config["value"]))
        return threshold

    def _apply_mitigations(self, threshold: float, mit_modifiers: dict, applied: set, item: dict) -> float:
        for slug, mit in mit_modifiers.items():
            if slug not in applied:
                continue
            target_type = mit.get("target_type")
            if target_type is None or target_type == item.get("type"):
                threshold = threshold * float(mit["factor"])
        return threshold
