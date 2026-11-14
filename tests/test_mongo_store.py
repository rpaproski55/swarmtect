"""Integration test against a REAL MongoDB server (local mongod or Atlas).
Skipped unless SWARMGUARD_MONGO_TEST_URI is set — never faked."""
import os
import pytest

URI = os.environ.get("SWARMGUARD_MONGO_TEST_URI")
pytestmark = pytest.mark.skipif(not URI, reason="SWARMGUARD_MONGO_TEST_URI not set")

def test_full_scenario_suite_on_mongo():
    from backend.app.store import MongoStore
    from backend.app.detector import Detector
    from simulator import scenarios
    s = MongoStore(URI, "swarmguard_pytest")
    try:
        for name, truth in [("S0", 0), ("S1", 0), ("S2", 1), ("S3", 1), ("S4", 1)]:
            s.clear()
            info = scenarios.SCENARIOS[name](s)
            assert info["truth_episodes"] == truth
            assert len(Detector(s).run("demo")) == truth, name
        s.clear()
        scenarios.run_s5(s)
        assert len(Detector(s).run("demo")) == 1
        assert len(Detector(s).run("tenant2")) == 1
    finally:
        s.clear()
