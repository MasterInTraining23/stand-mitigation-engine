import pytest
from engine.evaluators.boolean_condition import BooleanConditionEvaluator
from engine.evaluators.threshold_condition import ThresholdConditionEvaluator


class TestBooleanConditionEvaluator:
    def setup_method(self):
        self.ev = BooleanConditionEvaluator()

    def test_eq_passes(self):
        defn = {"condition": {"eq": [{"field": "roof_type"}, "Class A"]}}
        assert self.ev.evaluate(defn, {"roof_type": "Class A"}) is True

    def test_eq_fails(self):
        defn = {"condition": {"eq": [{"field": "roof_type"}, "Class A"]}}
        assert self.ev.evaluate(defn, {"roof_type": "Class B"}) is False

    def test_in_passes(self):
        defn = {"condition": {"in": [{"field": "roof_type"}, ["Class A", "Class B"]]}}
        assert self.ev.evaluate(defn, {"roof_type": "Class B"}) is True

    def test_in_fails(self):
        defn = {"condition": {"in": [{"field": "roof_type"}, ["Class A", "Class B"]]}}
        assert self.ev.evaluate(defn, {"roof_type": "Class C"}) is False

    def test_gte_passes(self):
        defn = {"condition": {"gte": [{"field": "home_to_home_distance"}, 15.0]}}
        assert self.ev.evaluate(defn, {"home_to_home_distance": 20}) is True

    def test_gte_fails(self):
        defn = {"condition": {"gte": [{"field": "home_to_home_distance"}, 15.0]}}
        assert self.ev.evaluate(defn, {"home_to_home_distance": 10}) is False

    def test_or_passes_when_one_branch_true(self):
        defn = {"condition": {"or": [
            {"eq": [{"field": "roof_type"}, "Class A"]},
            {"and": [
                {"eq": [{"field": "wildfire_risk_category"}, "A"]},
                {"in": [{"field": "roof_type"}, ["Class A", "Class B"]]},
            ]},
        ]}}
        # Class B roof in wildfire category A — should pass via second branch
        assert self.ev.evaluate(defn, {"roof_type": "Class B", "wildfire_risk_category": "A"}) is True

    def test_or_fails_when_no_branch_true(self):
        defn = {"condition": {"or": [
            {"eq": [{"field": "roof_type"}, "Class A"]},
            {"and": [
                {"eq": [{"field": "wildfire_risk_category"}, "A"]},
                {"in": [{"field": "roof_type"}, ["Class A", "Class B"]]},
            ]},
        ]}}
        # Class B roof in wildfire category B — should fail
        assert self.ev.evaluate(defn, {"roof_type": "Class B", "wildfire_risk_category": "B"}) is False

    def test_missing_field_returns_false(self):
        defn = {"condition": {"gte": [{"field": "home_to_home_distance"}, 15.0]}}
        assert self.ev.evaluate(defn, {}) is False

    def test_not_operator(self):
        defn = {"condition": {"not": {"eq": [{"field": "roof_type"}, "Class C"]}}}
        assert self.ev.evaluate(defn, {"roof_type": "Class A"}) is True
        assert self.ev.evaluate(defn, {"roof_type": "Class C"}) is False


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
        }

    def test_no_vegetation_passes(self):
        assert self.ev.evaluate(self.windows_defn, {"window_type": "Single"}) is True

    def test_tempered_glass_tree_passes_at_30ft(self):
        obs = {"window_type": "Tempered Glass", "vegetation": [{"type": "Tree", "distance_to_window": 31}]}
        assert self.ev.evaluate(self.windows_defn, obs) is True

    def test_tempered_glass_tree_fails_under_30ft(self):
        obs = {"window_type": "Tempered Glass", "vegetation": [{"type": "Tree", "distance_to_window": 29}]}
        assert self.ev.evaluate(self.windows_defn, obs) is False

    def test_single_pane_tree_threshold_is_90ft(self):
        # base 30 * 3 (single) * 1 (tree) = 90
        obs = {"window_type": "Single", "vegetation": [{"type": "Tree", "distance_to_window": 89}]}
        assert self.ev.evaluate(self.windows_defn, obs) is False

        obs["vegetation"][0]["distance_to_window"] = 91
        assert self.ev.evaluate(self.windows_defn, obs) is True

    def test_single_pane_shrub_threshold_is_45ft(self):
        # base 30 * 3 (single) / 2 (shrub) = 45
        obs = {"window_type": "Single", "vegetation": [{"type": "Shrub", "distance_to_window": 44}]}
        assert self.ev.evaluate(self.windows_defn, obs) is False

        obs["vegetation"][0]["distance_to_window"] = 46
        assert self.ev.evaluate(self.windows_defn, obs) is True

    def test_multiple_vegetation_items_all_must_pass(self):
        obs = {
            "window_type": "Tempered Glass",
            "vegetation": [
                {"type": "Tree", "distance_to_window": 31},   # passes (>30)
                {"type": "Tree", "distance_to_window": 25},   # fails (<30)
            ],
        }
        assert self.ev.evaluate(self.windows_defn, obs) is False

    def test_unknown_operation_raises(self):
        bad_defn = {
            "base_value": 30,
            "subject_field": "vegetation",
            "measurement_field": "distance_to_window",
            "modifiers": {"window_type": {"Single": {"op": "power", "value": 2}}},
        }
        with pytest.raises(ValueError, match="Unknown operation"):
            self.ev.evaluate(bad_defn, {"window_type": "Single", "vegetation": [{"type": "Tree", "distance_to_window": 10}]})
