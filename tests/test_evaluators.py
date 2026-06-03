import pytest
from engine.evaluators.boolean_condition import BooleanConditionEvaluator
from engine.evaluators.threshold_condition import ThresholdConditionEvaluator


class TestBooleanConditionEvaluator:
    def setup_method(self):
        self.ev = BooleanConditionEvaluator()

    def _passes(self, defn, obs):
        passes, details = self.ev.evaluate(defn, obs)
        assert details is None
        return passes

    def test_eq_passes(self):
        defn = {"condition": {"eq": [{"field": "roof_type"}, "Class A"]}}
        assert self._passes(defn, {"roof_type": "Class A"}) is True

    def test_eq_fails(self):
        defn = {"condition": {"eq": [{"field": "roof_type"}, "Class A"]}}
        assert self._passes(defn, {"roof_type": "Class B"}) is False

    def test_in_passes(self):
        defn = {"condition": {"in": [{"field": "roof_type"}, ["Class A", "Class B"]]}}
        assert self._passes(defn, {"roof_type": "Class B"}) is True

    def test_in_fails(self):
        defn = {"condition": {"in": [{"field": "roof_type"}, ["Class A", "Class B"]]}}
        assert self._passes(defn, {"roof_type": "Class C"}) is False

    def test_gte_passes(self):
        defn = {"condition": {"gte": [{"field": "home_to_home_distance"}, 15.0]}}
        assert self._passes(defn, {"home_to_home_distance": 20}) is True

    def test_gte_fails(self):
        defn = {"condition": {"gte": [{"field": "home_to_home_distance"}, 15.0]}}
        assert self._passes(defn, {"home_to_home_distance": 10}) is False

    def test_or_passes_when_one_branch_true(self):
        defn = {"condition": {"or": [
            {"eq": [{"field": "roof_type"}, "Class A"]},
            {"and": [
                {"eq": [{"field": "wildfire_risk_category"}, "A"]},
                {"in": [{"field": "roof_type"}, ["Class A", "Class B"]]},
            ]},
        ]}}
        assert self._passes(defn, {"roof_type": "Class B", "wildfire_risk_category": "A"}) is True

    def test_or_fails_when_no_branch_true(self):
        defn = {"condition": {"or": [
            {"eq": [{"field": "roof_type"}, "Class A"]},
            {"and": [
                {"eq": [{"field": "wildfire_risk_category"}, "A"]},
                {"in": [{"field": "roof_type"}, ["Class A", "Class B"]]},
            ]},
        ]}}
        assert self._passes(defn, {"roof_type": "Class B", "wildfire_risk_category": "B"}) is False

    def test_missing_field_returns_false(self):
        defn = {"condition": {"gte": [{"field": "home_to_home_distance"}, 15.0]}}
        assert self._passes(defn, {}) is False

    def test_not_operator(self):
        defn = {"condition": {"not": {"eq": [{"field": "roof_type"}, "Class C"]}}}
        assert self._passes(defn, {"roof_type": "Class A"}) is True
        assert self._passes(defn, {"roof_type": "Class C"}) is False


class TestThresholdConditionEvaluator:
    def setup_method(self):
        self.ev = ThresholdConditionEvaluator()
        self.windows_defn = {
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
            "mitigation_modifiers": {
                "apply_window_film":            {"factor": 0.8},
                "apply_flame_retardant_shrubs": {"factor": 0.75, "target_type": "Shrub"},
                "prune_trees":                  {"factor": 0.5,  "target_type": "Tree"},
            },
        }

    def _passes(self, obs):
        passes, _ = self.ev.evaluate(self.windows_defn, obs)
        return passes

    def _details(self, obs):
        _, details = self.ev.evaluate(self.windows_defn, obs)
        return details

    def test_no_vegetation_passes(self):
        passes, details = self.ev.evaluate(self.windows_defn, {"window_type": "Single"})
        assert passes is True
        assert details == []

    def test_tempered_glass_tree_passes_at_30ft(self):
        obs = {"window_type": "Tempered Glass", "vegetation": [{"type": "Tree", "distance_to_window": 31}]}
        assert self._passes(obs) is True

    def test_tempered_glass_tree_fails_under_30ft(self):
        obs = {"window_type": "Tempered Glass", "vegetation": [{"type": "Tree", "distance_to_window": 29}]}
        assert self._passes(obs) is False

    def test_single_pane_tree_threshold_is_90ft(self):
        obs = {"window_type": "Single", "vegetation": [{"type": "Tree", "distance_to_window": 89}]}
        assert self._passes(obs) is False
        obs["vegetation"][0]["distance_to_window"] = 91
        assert self._passes(obs) is True

    def test_single_pane_shrub_threshold_is_45ft(self):
        obs = {"window_type": "Single", "vegetation": [{"type": "Shrub", "distance_to_window": 44}]}
        assert self._passes(obs) is False
        obs["vegetation"][0]["distance_to_window"] = 46
        assert self._passes(obs) is True

    def test_multiple_vegetation_items_all_must_pass(self):
        obs = {
            "window_type": "Tempered Glass",
            "vegetation": [
                {"type": "Tree", "distance_to_window": 31},
                {"type": "Tree", "distance_to_window": 25},
            ],
        }
        assert self._passes(obs) is False

    def test_violation_details_included(self):
        obs = {"window_type": "Single", "vegetation": [{"type": "Tree", "distance_to_window": 25}]}
        details = self._details(obs)
        assert len(details) == 1
        assert details[0]["vegetation_type"] == "Tree"
        assert details[0]["actual_distance"] == 25.0
        assert details[0]["required_distance"] == 90.0
        assert details[0]["passes"] is False

    def test_window_film_reduces_threshold_for_all_vegetation(self):
        # base 90ft for single+tree; film applies to all → 90 * 0.8 = 72ft
        obs = {"window_type": "Single", "vegetation": [{"type": "Tree", "distance_to_window": 73}],
               "applied_mitigations": ["apply_window_film"]}
        assert self._passes(obs) is True

        obs["vegetation"][0]["distance_to_window"] = 71
        assert self._passes(obs) is False

    def test_prune_trees_only_affects_trees(self):
        # Tree threshold: 90 * 0.5 = 45ft; Shrub threshold: 45ft (unchanged)
        obs = {
            "window_type": "Single",
            "vegetation": [
                {"type": "Tree",  "distance_to_window": 46},
                {"type": "Shrub", "distance_to_window": 46},
            ],
            "applied_mitigations": ["prune_trees"],
        }
        assert self._passes(obs) is True

    def test_flame_retardant_only_affects_shrubs(self):
        # Shrub threshold: 45 * 0.75 = 33.75ft; Tree threshold: 90ft (unchanged)
        obs = {
            "window_type": "Single",
            "vegetation": [{"type": "Shrub", "distance_to_window": 34}],
            "applied_mitigations": ["apply_flame_retardant_shrubs"],
        }
        assert self._passes(obs) is True

    def test_stacked_mitigations(self):
        # Tree: 90 * 0.8 (film) * 0.5 (prune) = 36ft
        obs = {"window_type": "Single", "vegetation": [{"type": "Tree", "distance_to_window": 37}],
               "applied_mitigations": ["apply_window_film", "prune_trees"]}
        assert self._passes(obs) is True

        obs["vegetation"][0]["distance_to_window"] = 35
        assert self._passes(obs) is False

    def test_unknown_operation_raises(self):
        bad_defn = {
            "base_value": 30,
            "subject_field": "vegetation",
            "measurement_field": "distance_to_window",
            "modifiers": {"window_type": {"Single": {"op": "power", "value": 2}}},
        }
        with pytest.raises(ValueError, match="Unknown operation"):
            self.ev.evaluate(bad_defn, {"window_type": "Single", "vegetation": [{"type": "Tree", "distance_to_window": 10}]})
