from .base import BaseEvaluator

OPERATIONS = {
    "multiply": lambda a, b: a * b,
    "divide":   lambda a, b: a / b,
    "add":      lambda a, b: a + b,
    "subtract": lambda a, b: a - b,
}


class ThresholdConditionEvaluator(BaseEvaluator):
    def evaluate(self, definition: dict, observations: dict) -> bool:
        """
        Returns True if every item in subject_field is beyond its computed threshold.
        Returns True (no vulnerability) when subject_field is absent or empty.
        """
        subject_field = definition["subject_field"]
        measurement_field = definition["measurement_field"]
        base_value = float(definition["base_value"])
        modifiers = definition.get("modifiers", {})

        items = observations.get(subject_field) or []
        if not items:
            return True

        for item in items:
            threshold = self._compute_threshold(base_value, modifiers, observations, item)
            actual = float(item.get(measurement_field, 0))
            if actual < threshold:
                return False

        return True

    def _compute_threshold(self, base: float, modifiers: dict, observations: dict, item: dict) -> float:
        threshold = base
        for field, value_map in modifiers.items():
            # Top-level observation fields take precedence over item fields.
            # Documents a known limitation: avoid reusing field names across scopes.
            value = observations.get(field) if observations.get(field) is not None else item.get(field)
            if value is not None and value in value_map:
                op_config = value_map[value]
                op = OPERATIONS.get(op_config["op"])
                if op is None:
                    raise ValueError(f"Unknown operation: {op_config['op']}")
                threshold = op(threshold, float(op_config["value"]))
        return threshold
