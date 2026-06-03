from abc import ABC, abstractmethod
from typing import Any


class BaseEvaluator(ABC):
    @abstractmethod
    def evaluate(self, definition: dict, observations: dict) -> tuple[bool, Any]:
        """
        Returns (passes, details).
        passes=True means no vulnerability.
        details is evaluator-specific — None for boolean_condition,
        list of per-item results for threshold_condition.
        """
        pass
