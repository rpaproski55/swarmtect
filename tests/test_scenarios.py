from backend.app.detector import Detector, baseline_detect
from backend.app.gateway import Gateway
from simulator import scenarios

def test_s0_benign_independent_no_episode(store):
    scenarios.run_s0(store)
    assert Detector(store).run("demo") == []

def test_s1_benign_collaboration_not_quarantined(store):
    info = scenarios.run_s1(store)
    eps = Detector(store).run("demo")
    assert eps == []
    for aid in info["cohort"]:
        a = store.find_one("agents", {"_id": aid, "tenant_id": "demo"})
        assert a["status"] == "active"

def test_s2_attack_detected_blocked_quarantined(store):
    info = scenarios.run_s2(store)
    assert info["sensitive_result"]["decision"] == "deny"
    assert info["sensitive_result"]["executed"] is False
    # zero unauthorized effects in the ledger for the sensitive resource
    assert store.count("resource_ledger", {"resource_id": "sensitive_mock_dataset"}) == 0
    eps = Detector(store).run("demo")
    assert len(eps) == 1
    ep = eps[0]
    assert "R2_UNAUTHORIZED_BRIDGE" in ep["triggered_rules"]
    assert "R3_PROPAGATION" in ep["triggered_rules"]
    assert "R6_HIGH_IMPACT" in ep["triggered_rules"]
    assert set(info["cohort"]) <= set(ep["agent_ids"])
    assert ep["evidence_event_ids"], "episode must cite real event IDs"
    for ev_id in ep["evidence_event_ids"]:
        assert store.find_one("events", {"_id": ev_id}) is not None
    assert ep["status"] == "contained"
    for aid in info["cohort"]:
        a = store.find_one("agents", {"_id": aid, "tenant_id": "demo"})
        assert a["status"] == "quarantined"
    # an unrelated agent still works after containment
    gw = Gateway(store)
    others = [a for a in store.find("agents", {"tenant_id": "demo"}) if a["_id"] not in info["cohort"]]
    o = others[0]
    r = gw.execute_tool("demo", o["_id"], o["task_id"], "read_resource", "read", o["approved_resources"][0], "post_contain_1")
    assert r["decision"] == "allow"

def test_s3_fragments_detected_as_episode(store):
    scenarios.run_s3(store)
    eps = Detector(store).run("demo")
    assert len(eps) == 1
    assert "R3_PROPAGATION" in eps[0]["triggered_rules"]

def test_s4_trace_mismatch(store):
    scenarios.run_s4(store)
    eps = Detector(store).run("demo")
    assert len(eps) == 1
    assert "R5_TELEMETRY_MISMATCH" in eps[0]["triggered_rules"]

def test_s5_cross_tenant_isolation(store):
    scenarios.run_s5(store)
    eps_demo = Detector(store).run("demo")
    eps_t2 = Detector(store).run("tenant2")
    assert len(eps_demo) == 1 and len(eps_t2) == 1
    demo_agents = set(eps_demo[0]["agent_ids"]); t2_agents = set(eps_t2[0]["agent_ids"])
    # episodes reference only their own tenant's events
    for ep, tenant in ((eps_demo[0], "demo"), (eps_t2[0], "tenant2")):
        for ev_id in ep["evidence_event_ids"]:
            ev = store.find_one("events", {"_id": ev_id})
            assert ev["tenant_id"] == tenant

def test_baseline_misses_propagation_s3(store):
    """Matched comparison: baseline sees no direct violation in S3; Swarmtect detects the episode."""
    scenarios.run_s3(store)
    assert baseline_detect(store, "demo") == []
    assert len(Detector(store).analyze("demo")) == 1

def test_no_truth_labels_on_events(store):
    scenarios.run_s2(store)
    for e in store.find("events", {"tenant_id": "demo"}):
        assert "simulator_truth_label" not in e
        assert "simulator_truth_label" not in (e.get("metadata") or {})
