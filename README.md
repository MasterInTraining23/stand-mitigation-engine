# Stand Mitigation Rules Engine

A proof-of-concept mitigation rules engine for property insurance underwriting.
Evaluates a property's observations against a versioned database of underwriting rules,
identifies vulnerabilities, and recommends mitigations.

## Quickstart

```bash
docker-compose up --build
```

Open [http://localhost:8000](http://localhost:8000) — the app is running.
API docs available at [http://localhost:8000/docs](http://localhost:8000/docs).

The database is seeded on first start with the four example rules from the spec.

---

## Overview of Selected Stack

| Layer | Choice | Rationale |
|---|---|---|
| **API** | FastAPI | Native Pydantic validation, automatic OpenAPI docs, async-ready |
| **ORM** | SQLAlchemy (sync) | Postgres migration is a single connection string change — no code changes |
| **Database** | SQLite | Zero-setup for local dev and demo; sufficient for expected rule volume (<2,000 active rules) |
| **Containerisation** | Docker + docker-compose | Evaluators run the demo with `docker-compose up`. Same image deploys to ECS/Kubernetes. |
| **Frontend** | Vanilla JS, no build step | Served directly from FastAPI static files; no Node/npm dependency; sufficient for demo |

**On Python vs. Java/Rust:** evaluation overhead is a negligible fraction of the total
request round-trip (DB query + network latency dominate). Python is suitable for the
foreseeable future at expected rule volumes. See `docs/design-decisions.md` for the
full performance reasoning.

---

## Architecture Overview

```
Browser
  ├── Underwriter tab  →  POST /evaluate
  └── Applied Science tab  →  /admin/rules (CRUD + transitions + test)

FastAPI Application (Docker container)
  ├── api/routers/
  │   ├── evaluate.py        POST /evaluate
  │   ├── rules.py           GET /rules, GET /rules/{slug}/mitigations
  │   └── admin.py           /admin/rules CRUD + lifecycle
  ├── engine/
  │   ├── evaluator.py       Orchestrates: load rules → dispatch → collect results
  │   ├── cache.py           In-memory active ruleset cache (invalidated on state change)
  │   └── evaluators/
  │       ├── boolean_condition.py   Recursive condition tree walker
  │       └── threshold_condition.py Base value + modifier arithmetic
  └── db/
      ├── models.py          Rule, Mitigation, RuleAuditLog
      ├── queries.py         Time-aware active rule queries
      └── seed.py            Seeds the 4 spec example rules on first start

SQLite (Docker volume: ./data/db.sqlite)
```

**Key design patterns:**

- **Hybrid typed evaluators + data:** Rules are stored as data (`definition` JSON blob).
  A `type` field dispatches to a named evaluator class. Simple rules use `boolean_condition`;
  distance/threshold rules use `threshold_condition`. Adding a new evaluator type is one
  new class + one dict entry — no changes to routing or orchestration.

- **Append-only versioning:** "Updating" an activated rule creates a new row (returning
  to `draft`) and atomically deactivates the previous version on activation. A rule's
  stable identity across versions is its `slug`.

- **State machine:** `draft → under_review → activated → deactivated`. Invalid transitions
  are rejected with `422` before touching the database. All transitions are logged to
  `rule_audit_log` with author, timestamp, and note.

- **ACID transactions:** SQLite guarantees that deactivating the old version and activating
  the new version are atomic. No partially-applied rule updates.

---

## High-Level Functionality Overview

### Underwriter Flow

1. Open the **Underwriter** tab
2. Fill in property observations (attic vent, roof type, window type, wildfire risk,
   home-to-home distance, vegetation items with distances)
3. Optionally set an **As-Of date** to evaluate against historical rules
4. Click **Evaluate Property**
5. Results show:
   - A green pass banner if no vulnerabilities
   - Vulnerability cards grouped by category, each with:
     - Full mitigations (green) — completely resolve the vulnerability
     - Bridge mitigations (yellow) — partial fixes; subject to policy limits
     - Unmitigatable (red) — property characteristic that cannot be changed

### Applied Science Flow

1. Open the **Applied Science** tab — shows all rules across all statuses
2. **Create** a new rule: click `+ New Rule`, fill in slug, category, name, written rule,
   evaluator type, and JSON definition; saves as `draft`
3. **Edit** a draft rule in place
4. **Test** a draft or under-review rule against sample observations before activating
5. **Transition** rules through the lifecycle:
   - `draft → under review → activated` (activating auto-deactivates the prior version)
   - Any status → `deactivated`
6. **View** rule detail: definition JSON, mitigations, and full audit log
7. **History:** view all versions of a rule by slug at `/admin/rules/slug/{slug}/history`

### API (for integrations)

Full OpenAPI spec at `/docs`. Key endpoints:

- `POST /evaluate` — evaluate a property; accepts `as_of` for historical queries
- `GET /rules` — list active rules in human-readable format
- `GET /rules/{slug}/mitigations` — all mitigations for a rule
- `POST /admin/rules/{id}/test` — test a draft rule without affecting production

---

## Evaluator Types

### `boolean_condition`

Evaluates a recursive condition tree. Supports: `eq`, `in`, `gte`, `lte`, `and`, `or`, `not`.

```json
{
  "condition": {
    "or": [
      { "eq": [{ "field": "roof_type" }, "Class A"] },
      { "and": [
          { "eq": [{ "field": "wildfire_risk_category" }, "A"] },
          { "in": [{ "field": "roof_type" }, ["Class A", "Class B"]] }
      ]}
    ]
  }
}
```

### `threshold_condition`

Computes a dynamic threshold from a base value and a set of arithmetic modifiers,
then compares each item in a subject array against that threshold.

Supported operations: `multiply`, `divide`, `add`, `subtract`.

```json
{
  "base_value": 30,
  "subject_field": "vegetation",
  "measurement_field": "distance_to_window",
  "modifiers": {
    "window_type": {
      "Single":         { "op": "multiply", "value": 3 },
      "Tempered Glass": { "op": "multiply", "value": 1 }
    },
    "type": {
      "Tree":  { "op": "multiply", "value": 1 },
      "Shrub": { "op": "divide",   "value": 2 }
    }
  }
}
```

---

## Future Works

- **Rule conflict detection:** Automatically flag rules with overlapping slugs or
  contradictory conditions at validation time.

- **Postgres migration:** Swap the SQLite connection string for Postgres when SQLite's
  single-writer lock becomes a concurrency bottleneck under high request volume.
  No application code changes required by design.

- **Multi-worker cache:** The in-memory rule cache is per-process. For multi-worker
  deployments, replace with a shared Redis cache invalidated via pub/sub on rule
  state changes.

- **DSL for rule definitions:** A full expression language for rule conditions if the
  four-operation vocabulary (`multiply`, `divide`, `add`, `subtract`) proves insufficient.
  Requires governance infrastructure (linter, sandbox, review tooling) before adoption.

- **Persistent evaluation history:** Store evaluation results per policy/property for
  audit purposes. Currently the engine evaluates on demand; persistence belongs in a
  policy management system.

- **Authentication and authorisation:** Underwriter and Applied Science routes should
  sit behind role-based auth in production.

- **Rule testing sandbox enhancements:** A richer test interface with multiple sample
  observations, expected-outcome assertions, and batch test runs.

- **CDN/edge caching:** If underwriter traffic scales significantly, evaluation results
  could be cached at the edge for a short TTL. Not warranted at current expected volume.
