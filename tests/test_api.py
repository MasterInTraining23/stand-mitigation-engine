import json
import pytest


ROOF_RULE = {
    "slug": "roof_class",
    "category": "roof",
    "name": "Roof — Class Rating",
    "written_rule": "Roof must be Class A. Class B is acceptable in wildfire category A.",
    "type": "boolean_condition",
    "definition": {
        "condition": {
            "or": [
                {"eq": [{"field": "roof_type"}, "Class A"]},
                {"and": [
                    {"eq": [{"field": "wildfire_risk_category"}, "A"]},
                    {"in": [{"field": "roof_type"}, ["Class A", "Class B"]]},
                ]},
            ]
        }
    },
    "author_id": "test_user",
    "author_name": "Test User",
    "mitigations": [
        {"type": "full", "name": "Replace Roof", "description": "Upgrade to Class A."}
    ],
}


def create_and_activate_rule(client, rule_payload):
    res = client.post("/admin/rules", json=rule_payload)
    assert res.status_code == 201
    rule_id = res.json()["id"]
    tr1 = client.post(f"/admin/rules/{rule_id}/transition", json={
        "to_status": "under_review", "author_id": "test_user", "author_name": "Test User"
    })
    assert tr1.status_code == 200
    tr2 = client.post(f"/admin/rules/{rule_id}/transition", json={
        "to_status": "activated", "author_id": "test_user", "author_name": "Test User"
    })
    assert tr2.status_code == 200
    return rule_id


class TestEvaluationEndpoint:
    def test_no_vulnerabilities_when_no_rules(self, client):
        res = client.post("/evaluate", json={"observations": {"roof_type": "Class B"}})
        assert res.status_code == 200
        assert res.json()["vulnerabilities"] == []

    def test_detects_roof_vulnerability(self, client):
        create_and_activate_rule(client, ROOF_RULE)
        res = client.post("/evaluate", json={"observations": {"roof_type": "Class B", "wildfire_risk_category": "B"}})
        assert res.status_code == 200
        vulns = res.json()["vulnerabilities"]
        assert len(vulns) == 1
        assert vulns[0]["rule_slug"] == "roof_class"
        assert len(vulns[0]["full_mitigations"]) == 1

    def test_no_vulnerability_when_rule_passes(self, client):
        create_and_activate_rule(client, ROOF_RULE)
        res = client.post("/evaluate", json={"observations": {"roof_type": "Class A"}})
        assert res.status_code == 200
        assert res.json()["vulnerabilities"] == []

    def test_as_of_before_activation_returns_empty(self, client):
        create_and_activate_rule(client, ROOF_RULE)
        res = client.post("/evaluate", json={
            "observations": {"roof_type": "Class B", "wildfire_risk_category": "B"},
            "as_of": "2000-01-01T00:00:00Z",
        })
        assert res.status_code == 200
        assert res.json()["vulnerabilities"] == []


class TestAdminRules:
    def test_create_rule_starts_as_draft(self, client):
        res = client.post("/admin/rules", json=ROOF_RULE)
        assert res.status_code == 201
        assert res.json()["status"] == "draft"

    def test_draft_rule_not_in_evaluation(self, client):
        client.post("/admin/rules", json=ROOF_RULE)
        res = client.post("/evaluate", json={"observations": {"roof_type": "Class C"}})
        assert res.json()["vulnerabilities"] == []

    def test_valid_transition_draft_to_under_review(self, client):
        rule_id = client.post("/admin/rules", json=ROOF_RULE).json()["id"]
        res = client.post(f"/admin/rules/{rule_id}/transition", json={
            "to_status": "under_review", "author_id": "u", "author_name": "User"
        })
        assert res.status_code == 200
        assert res.json()["status"] == "under_review"

    def test_invalid_transition_raises_422(self, client):
        rule_id = client.post("/admin/rules", json=ROOF_RULE).json()["id"]
        res = client.post(f"/admin/rules/{rule_id}/transition", json={
            "to_status": "activated", "author_id": "u", "author_name": "User"
        })
        assert res.status_code == 422

    def test_activating_new_version_deactivates_old(self, client):
        rule_id_v1 = create_and_activate_rule(client, ROOF_RULE)

        v2 = {**ROOF_RULE, "change_note": "Version 2"}
        rule_id_v2 = create_and_activate_rule(client, v2)

        v1 = client.get(f"/admin/rules/{rule_id_v1}").json()
        assert v1["status"] == "deactivated"

        v2_rule = client.get(f"/admin/rules/{rule_id_v2}").json()
        assert v2_rule["status"] == "activated"

    def test_update_only_allowed_on_draft(self, client):
        rule_id = create_and_activate_rule(client, ROOF_RULE)
        res = client.put(f"/admin/rules/{rule_id}", json={
            "name": "Updated Name", "author_id": "u", "author_name": "User"
        })
        assert res.status_code == 422

    def test_test_endpoint_works_on_draft(self, client):
        rule_id = client.post("/admin/rules", json=ROOF_RULE).json()["id"]
        res = client.post(f"/admin/rules/{rule_id}/test", json={
            "observations": {"roof_type": "Class B", "wildfire_risk_category": "B"}
        })
        assert res.status_code == 200
        assert res.json()["vulnerability_triggered"] is True

    def test_test_endpoint_blocked_on_activated(self, client):
        rule_id = create_and_activate_rule(client, ROOF_RULE)
        res = client.post(f"/admin/rules/{rule_id}/test", json={"observations": {}})
        assert res.status_code == 422

    def test_audit_log_records_transitions(self, client):
        rule_id = create_and_activate_rule(client, ROOF_RULE)
        logs = client.get(f"/admin/rules/{rule_id}/audit").json()
        statuses = [l["to_status"] for l in logs]
        assert "activated" in statuses

    def test_rule_history_by_slug(self, client):
        create_and_activate_rule(client, ROOF_RULE)
        create_and_activate_rule(client, {**ROOF_RULE, "change_note": "v2"})
        history = client.get(f"/admin/rules/slug/{ROOF_RULE['slug']}/history").json()
        assert len(history) == 2

    def test_reactivate_deactivated_rule(self, client):
        rule_id = create_and_activate_rule(client, ROOF_RULE)
        client.post(f"/admin/rules/{rule_id}/transition", json={
            "to_status": "deactivated", "author_id": "u", "author_name": "User"
        })
        res = client.post(f"/admin/rules/{rule_id}/transition", json={
            "to_status": "activated", "author_id": "u", "author_name": "User"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "activated"
        assert data["deactivated_at"] is None  # must be cleared on reactivation

    def test_reactivated_rule_evaluates(self, client):
        rule_id = create_and_activate_rule(client, ROOF_RULE)
        client.post(f"/admin/rules/{rule_id}/transition", json={
            "to_status": "deactivated", "author_id": "u", "author_name": "User"
        })
        # deactivated — should not evaluate
        res = client.post("/evaluate", json={"observations": {"roof_type": "Class C"}})
        assert res.json()["vulnerabilities"] == []

        client.post(f"/admin/rules/{rule_id}/transition", json={
            "to_status": "activated", "author_id": "u", "author_name": "User"
        })
        # reactivated — should evaluate again
        res = client.post("/evaluate", json={"observations": {"roof_type": "Class C"}})
        assert len(res.json()["vulnerabilities"]) == 1
