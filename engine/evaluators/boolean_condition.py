from .base import BaseEvaluator


class BooleanConditionEvaluator(BaseEvaluator):
    def evaluate(self, definition: dict, observations: dict) -> bool:
        return self._eval_node(definition["condition"], observations)

    def _eval_node(self, node: dict, observations: dict) -> bool:
        if "and" in node:
            return all(self._eval_node(child, observations) for child in node["and"])
        if "or" in node:
            return any(self._eval_node(child, observations) for child in node["or"])
        if "not" in node:
            return not self._eval_node(node["not"], observations)
        if "eq" in node:
            left, right = node["eq"]
            return self._resolve(left, observations) == right
        if "in" in node:
            left, right = node["in"]
            return self._resolve(left, observations) in right
        if "gte" in node:
            left, right = node["gte"]
            val = self._resolve(left, observations)
            return val is not None and float(val) >= float(right)
        if "lte" in node:
            left, right = node["lte"]
            val = self._resolve(left, observations)
            return val is not None and float(val) <= float(right)
        raise ValueError(f"Unknown condition operator: {list(node.keys())}")

    def _resolve(self, operand, observations: dict):
        if isinstance(operand, dict) and "field" in operand:
            return observations.get(operand["field"])
        return operand
