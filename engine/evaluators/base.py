from abc import ABC, abstractmethod


class BaseEvaluator(ABC):
    @abstractmethod
    def evaluate(self, definition: dict, observations: dict) -> bool:
        """Returns True if the rule PASSES (no vulnerability), False if vulnerability is triggered."""
        pass
