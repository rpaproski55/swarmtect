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
    def clear(self, preserve=()):
        for c in COLLECTIONS:
            if c not in preserve: self.data[c] = []

class MongoStore:
    backend = "mongodb-atlas"
    def __init__(self, uri: str, db_name: str = "swarmguard"):
        from pymongo import MongoClient
        self.client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        self.client.admin.command("ping")  # fail loudly, never fake Atlas
        self.db = self.client[db_name]
    def insert(self, coll, doc):
        d = copy.deepcopy(doc); self.db[coll].insert_one(copy.deepcopy(d)); return d
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
    def clear(self, preserve=()):
        for c in COLLECTIONS:
            if c not in preserve: self.db[c].delete_many({})

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
