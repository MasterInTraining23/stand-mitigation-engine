import threading
from typing import Optional
from sqlalchemy.orm import selectinload


class RuleCache:
    """
    In-process singleton cache of the active ruleset.
    Historical queries (as_of) always bypass the cache and hit the DB directly.
    Cache is invalidated on any rule activation or deactivation.
    Note: per-process cache — if running multiple uvicorn workers, each worker
    maintains its own cache. Acceptable for single-worker POC; use Redis for multi-worker.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._cache = None
        return cls._instance

    def get_active_rules(self, db, from_date: Optional[int] = None, to_date: Optional[int] = None):
        from db.queries import query_active_rules, query_active_rules_in_range, query_active_rules_at
        if from_date is not None and to_date is not None:
            return query_active_rules_in_range(db, from_date, to_date)
        if from_date is not None:
            return query_active_rules_at(db, from_date)
        if to_date is not None:
            return query_active_rules_at(db, to_date)
        if self._cache is None:
            from db.models import Rule
            rules = (
                db.query(Rule)
                .options(selectinload(Rule.mitigations))
                .filter(Rule.status == "activated")
                .all()
            )
            # Expunge from session so cached objects survive across requests
            # without triggering lazy-load on a closed session.
            for rule in rules:
                for m in rule.mitigations:
                    db.expunge(m)
                db.expunge(rule)
            self._cache = rules
        return self._cache

    def invalidate(self):
        self._cache = None


rule_cache = RuleCache()
