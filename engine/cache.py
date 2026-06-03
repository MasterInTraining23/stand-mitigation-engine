import threading
from typing import Optional


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

    def get_active_rules(self, db, as_of=None):
        from db.queries import query_active_rules, query_active_rules_at
        if as_of is not None:
            return query_active_rules_at(db, as_of)
        if self._cache is None:
            self._cache = query_active_rules(db)
        return self._cache

    def invalidate(self):
        self._cache = None


rule_cache = RuleCache()
