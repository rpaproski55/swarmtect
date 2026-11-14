"""Store abstraction: in-memory for tests/local, MongoDB Atlas when MONGODB_URI is set.

Both implement the same tiny interface so gateway/detector code is identical.
The in-memory store is NOT presented as Atlas — STATUS.md labels it a fallback.
"""
from __future__ import annotations
import copy, os
from typing import Any

COLLECTIONS = ["agents","tasks","policies","artifacts","events","gateway_effects",
               "episodes","incident_actions","verified_cases","runs","resource_ledger"]
# self_reports is created lazily by MemoryStore via setdefault in gateway usage;
# include it explicitly:
COLLECTIONS = COLLECTIONS + ["self_reports"]

def _match(doc: dict, filt: dict) -> bool:
    for k, v in filt.items():
        dv = doc.get(k)
        if isinstance(v, dict) and "$in" in v:
            if dv not in v["$in"]:
                return False
        elif dv != v:
            return False
    return True

class MemoryStore:
    backend = "memory"
    def __init__(self):
        self.data: dict[str, list[dict]] = {c: [] for c in COLLECTIONS}
        self._seq: dict[str, int] = {}
    def insert(self, coll: str, doc: dict) -> dict:
        d = copy.deepcopy(doc); self.data[coll].append(d); return copy.deepcopy(d)
    def find(self, coll: str, filt: dict | None = None) -> list[dict]:
        filt = filt or {}
        return [copy.deepcopy(d) for d in self.data[coll] if _match(d, filt)]
    def find_one(self, coll: str, filt: dict) -> dict | None:
        r = self.find(coll, filt)
        return r[0] if r else None
    def update(self, coll: str, filt: dict, changes: dict) -> dict | None:
        for d in self.data[coll]:
            if _match(d, filt):
                d.update(copy.deepcopy(changes)); return copy.deepcopy(d)
        return None
    def count(self, coll: str, filt: dict | None = None) -> int:
        return len(self.find(coll, filt))
    def next_seq(self, tenant_id: str) -> int:
        """Per-tenant monotonic event sequence (ordering never relies on ISO timestamp strings)."""
        self._seq[tenant_id] = self._seq.get(tenant_id, 0) + 1
        return self._seq[tenant_id]
    def clear(self, preserve=(), tenant_id=None):
        """Delete demo data. With tenant_id, only that tenant's documents (other tenants untouched)."""
        for c in COLLECTIONS:
            if c in preserve: continue
            self.data[c] = [] if tenant_id is None else [d for d in self.data[c] if d.get("tenant_id") != tenant_id]

class MongoStore:
    backend = "mongodb-atlas"
    def __init__(self, uri: str, db_name: str = "swarmguard"):
        from pymongo import MongoClient
        self.client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        self.client.admin.command("ping")  # fail loudly, never fake Atlas
        self.db = self.client[db_name]
    def insert(self, coll, doc):
        from pymongo.errors import DuplicateKeyError
        d = copy.deepcopy(doc)
        try:
            self.db[coll].insert_one(copy.deepcopy(d))
        except DuplicateKeyError:
            if coll != "gateway_effects":
                raise
            # concurrent duplicate of the same (tenant, agent, action_id): return the stored effect
            existing = self.db[coll].find_one({k: d.get(k) for k in ("tenant_id", "agent_id", "action_id")})
            return existing or d
        return d
    def find(self, coll, filt=None):
        # Our docs use a string _id (e.g. evt_...), which is also Mongo's _id — return it as-is.
        return list(self.db[coll].find(filt or {}))
    def find_one(self, coll, filt):
        return self.db[coll].find_one(filt)
    def update(self, coll, filt, changes):
        self.db[coll].update_one(filt, {"$set": changes})
        return self.find_one(coll, filt)
    def count(self, coll, filt=None):
        return self.db[coll].count_documents(filt or {})
    def next_seq(self, tenant_id):
        from pymongo import ReturnDocument
        doc = self.db["counters"].find_one_and_update({"_id": f"seq:{tenant_id}"}, {"$inc": {"seq": 1}},
                                                      upsert=True, return_document=ReturnDocument.AFTER)
        return doc["seq"]
    def clear(self, preserve=(), tenant_id=None):
        filt = {} if tenant_id is None else {"tenant_id": tenant_id}
        for c in COLLECTIONS:
            if c not in preserve: self.db[c].delete_many(filt)

class BatchingStore(MemoryStore):
    """Run-scoped write-behind wrapper over MongoStore for demo scenario runs.

    A demo click makes ~150 small reads/writes; at ~80 ms per Atlas round trip
    that is 10+ seconds. This keeps the run's working set in memory (the same
    gateway + detector code runs unchanged), then persists everything to Atlas
    in bulk on flush(): parallel clears, then one insert_many per collection.
    Everything the cockpit displays is still read back from Atlas afterwards.
    Live API paths (/api/tool/execute, artifact routes) keep writing per call.
    """
    backend = "mongodb-atlas"

    def __init__(self, inner: "MongoStore", preload=("verified_cases",)):
        super().__init__()
        self.inner, self.db = inner, inner.db
        self._cleared: set[tuple] = set()   # (collection, tenant_id or None for all)
        self._inserted: dict[str, list] = {c: [] for c in COLLECTIONS}
        self._updates: list[tuple[str, dict, dict]] = []
        for c in preload:  # small, needed for case-memory lookups during detection
            self.data[c] = list(inner.db[c].find({}))

    def insert(self, coll, doc):
        d = super().insert(coll, doc)
        self._inserted[coll].append(d["_id"])
        return d

    def next_seq(self, tenant_id):
        if tenant_id not in self._seq:
            c = self.db["counters"].find_one({"_id": f"seq:{tenant_id}"}) if hasattr(self.db["counters"], "find_one") else None
            self._seq[tenant_id] = (c or {}).get("seq", 0)
            self._seq_touched = getattr(self, "_seq_touched", set())
        self._seq_touched = getattr(self, "_seq_touched", set()) | {tenant_id}
        return super().next_seq(tenant_id)

    def update(self, coll, filt, changes):
        d = super().update(coll, filt, changes)
        if d is not None and d["_id"] not in self._inserted[coll]:
            self._updates.append((coll, filt, changes))  # doc predates this run: patch it in Atlas
        return d

    def clear(self, preserve=(), tenant_id=None):
        super().clear(preserve, tenant_id)
        for c in COLLECTIONS:
            if c not in preserve:
                self._cleared.add((c, tenant_id))
                keep = {d["_id"] for d in self.data[c]}
                self._inserted[c] = [i for i in self._inserted[c] if i in keep]
        self._updates = [u for u in self._updates if u[0] in preserve]

    def flush(self) -> dict:
        from concurrent.futures import ThreadPoolExecutor
        ids_by_coll = {c: set(ids) for c, ids in self._inserted.items() if ids}
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(lambda ct: self.db[ct[0]].delete_many({} if ct[1] is None else {"tenant_id": ct[1]}),
                          sorted(self._cleared, key=lambda ct: (ct[0], ct[1] or ""))))
            def write(c):
                docs = [d for d in self.data[c] if d["_id"] in ids_by_coll[c]]
                if docs:
                    self.db[c].insert_many(docs, ordered=False)
                return len(docs)
            counts = dict(zip(ids_by_coll, pool.map(write, list(ids_by_coll))))
        for coll, filt, changes in self._updates:
            self.db[coll].update_one(filt, {"$set": changes})
        for t in getattr(self, "_seq_touched", set()):
            # $max keeps the counter monotonic even if a live call advanced it meanwhile
            self.db["counters"].update_one({"_id": f"seq:{t}"}, {"$max": {"seq": self._seq[t]}}, upsert=True)
        self._seq_touched = set()
        written = {"cleared": sorted({f"{c}:{t or '*'}" for c, t in self._cleared}), "inserted": counts, "updated": len(self._updates)}
        self._cleared, self._updates = set(), []
        self._inserted = {c: [] for c in COLLECTIONS}
        return written

def load_env() -> None:
    """Load .env from the repo root so MONGODB_URI etc. are picked up.
    Real environment variables win. Skipped under pytest (see tests/conftest.py)."""
    if os.environ.get("SWARMGUARD_SKIP_DOTENV"):
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(override=False)

def get_store() -> Any:
    load_env()
    uri = os.environ.get("MONGODB_URI", "").strip()
    if uri:
        return MongoStore(uri, os.environ.get("MONGODB_DB", "swarmguard"))
    return MemoryStore()
