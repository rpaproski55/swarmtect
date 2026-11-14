"""BatchingStore must give the same detection results as the plain stores, and
persist the run with a handful of bulk calls instead of one call per document."""
from backend.app.store import BatchingStore, MemoryStore
from backend.app.detector import Detector
from simulator import scenarios


class FakeColl:
    def __init__(self, log, name):
        self.docs, self.log, self.name = [], log, name
    def find(self, filt):
        self.log.append(("find", self.name)); return [dict(d) for d in self.docs]
    def delete_many(self, filt):
        self.log.append(("delete_many", self.name)); self.docs = []
    def insert_many(self, docs, ordered=True):
        self.log.append(("insert_many", self.name)); self.docs += [dict(d) for d in docs]
    def update_one(self, filt, upd):
        self.log.append(("update_one", self.name))
        for d in self.docs:
            if all(d.get(k) == v for k, v in filt.items()):
                d.update(upd["$set"]); return


class FakeDB(dict):
    def __init__(self):
        super().__init__(); self.log = []
    def __missing__(self, name):
        self[name] = FakeColl(self.log, name); return self[name]


class FakeMongo:
    backend = "mongodb-atlas"
    def __init__(self):
        self.db = FakeDB()


def _run(store, name):
    info = scenarios.SCENARIOS[name](store)
    return info, Detector(store).run("demo")


def test_batched_run_matches_memory_and_uses_few_round_trips():
    for name in ["S0", "S1", "S2", "S3", "S4"]:
        _, expected = _run(MemoryStore(), name)
        atlas = FakeMongo()
        bs = BatchingStore(atlas)
        _, got = _run(bs, name)
        bs.flush()
        assert [sorted(e["triggered_rules"]) for e in got] == [sorted(e["triggered_rules"]) for e in expected], name
        # persisted state equals the in-run state
        for coll in ("events", "episodes", "agents", "gateway_effects"):
            assert len(atlas.db[coll].docs) == len(bs.data[coll]), (name, coll)
        assert len(atlas.db.log) <= 30, (name, len(atlas.db.log))


def test_quarantine_status_is_persisted():
    atlas = FakeMongo()
    bs = BatchingStore(atlas)
    _run(bs, "S2")
    bs.flush()
    quarantined = [a["_id"] for a in atlas.db["agents"].docs if a["status"] == "quarantined"]
    assert len(quarantined) == 5


def test_s2_story_includes_goal_drift():
    _, eps = _run(MemoryStore(), "S2")
    assert len(eps) == 1
    assert {"R1_POLICY_BREACH", "R2_UNAUTHORIZED_BRIDGE", "R3_PROPAGATION",
            "R4_GOAL_DRIFT", "R6_HIGH_IMPACT"} <= set(eps[0]["triggered_rules"])


# ---- API-level checks against a Mongo-like store that enforces the real unique index ----
import threading
import pytest


class DupKey(Exception):
    pass


class StrictColl(FakeColl):
    """FakeColl + the Atlas unique index on gateway_effects (tenant_id, action_id) + $in filters."""
    lock = threading.Lock()
    def _m(self, d, filt):
        for k, v in (filt or {}).items():
            if isinstance(v, dict) and "$in" in v:
                if d.get(k) not in v["$in"]: return False
            elif d.get(k) != v: return False
        return True
    def find(self, filt=None):
        self.log.append(("find", self.name)); return [dict(d) for d in list(self.docs) if self._m(d, filt)]
    def find_one(self, filt):
        r = self.find(filt); return r[0] if r else None
    def insert_many(self, docs, ordered=True):
        with StrictColl.lock:
            if self.name == "gateway_effects":
                seen = {(d["tenant_id"], d["action_id"]) for d in self.docs}
                for d in docs:
                    if (d["tenant_id"], d["action_id"]) in seen:
                        raise DupKey("E11000 duplicate key gateway_effects tenant_id_1_action_id_1")
            self.docs += [dict(d) for d in docs]
    def insert_one(self, d):
        self.insert_many([d])


class StrictDB(FakeDB):
    def __missing__(self, name):
        self[name] = StrictColl(self.log, name); return self[name]


class FakeMongoStore:
    """Stand-in for MongoStore (same interface the app uses) backed by StrictDB."""
    backend = "mongodb-atlas"
    def __init__(self):
        self.db = StrictDB()
        self.client = type("C", (), {"admin": type("A", (), {"command": staticmethod(lambda *a, **k: {"ok": 1})})()})()
    def insert(self, c, d): self.db[c].insert_one(d); return dict(d)
    def find(self, c, f=None): return self.db[c].find(f)
    def find_one(self, c, f): return self.db[c].find_one(f)
    def update(self, c, f, ch):
        for d in self.db[c].docs:
            if self.db[c]._m(d, f): d.update(ch); return dict(d)
    def count(self, c, f=None): return len(self.find(c, f))
    def clear(self, preserve=()):
        from backend.app.store import COLLECTIONS
        for c in COLLECTIONS:
            if c not in preserve: self.db[c].delete_many({})


@pytest.fixture()
def atlas_app(monkeypatch):
    import backend.app.main as M
    monkeypatch.setattr(M, "store", FakeMongoStore())
    from fastapi.testclient import TestClient
    return TestClient(M.app, raise_server_exceptions=False)


H = {"x-operator-secret": "demo-operator-secret-change-me"}


def test_demo_page_flow_on_atlas_path(atlas_app):
    c = atlas_app
    assert c.post("/api/demo/run", headers=H, json={"scenario": "S1"}).json()["episodes_detected"] == 0
    r = c.post("/api/demo/run", headers=H, json={"scenario": "S2"}); assert r.status_code == 200, r.text
    ep = r.json()["episodes"][0]
    assert "R4_GOAL_DRIFT" in ep["triggered_rules"]
    d = c.get(f"/api/episodes/{ep['_id']}").json()
    assert any(not f["executed"] for f in d["effects"]) and d["artifacts"]
    assert c.post(f"/api/episodes/{ep['_id']}/confirm", headers=H).status_code == 200
    assert c.post("/api/demo/run", headers=H, json={"scenario": "S2"}).status_code == 200
    assert c.post("/api/demo/run", headers=H, json={"scenario": "S6"}).status_code == 200
    assert c.get("/api/events").status_code == 200 and c.get("/api/agents").status_code == 200


def test_overlapping_demo_runs_do_not_collide(atlas_app):
    c = atlas_app
    codes = []
    def go(sc):
        codes.append(c.post("/api/demo/run", headers=H, json={"scenario": sc}).status_code)
    ts = [threading.Thread(target=go, args=(sc,)) for sc in ["S2", "S1", "S2", "S6", "S2", "S1"]]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert codes == [200] * 6, codes
