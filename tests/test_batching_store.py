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
