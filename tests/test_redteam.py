"""Red-team regression suite for Swarmtect.

Every test here encodes an attack or failure that WORKS against commit c05a400.
They are expected to FAIL until the matching work item in
SWARMGUARD_CLAUDE_CODE_PROMPT.md is implemented. Do not weaken a test to make
it pass; if an interface name must change, change it here and say why in the
commit message.

Run one tier at a time:
    .venv/bin/python -m pytest -q tests/test_redteam.py -m p0
    .venv/bin/python -m pytest -q tests/test_redteam.py -m p1

Interfaces these tests assume (defined in the prompt, section "Contracts"):
  - backend/app/identity.py: issue_agent_key(tenant_id, agent_id) -> str
  - HTTP agent routes require header  x-agent-key
  - store.clear(preserve=(), tenant_id=None)  -> tenant-scoped when tenant_id given
  - Detector(store, rules=None)  -> rules dict overrides configs/rules.yaml
  - episodes carry: status in {"watch","alert","contained","confirmed","dismissed"},
    episode_key (stable), exposed_agent_ids (list)
  - agent status may be "restricted" (normal work allowed, high-impact denied)
"""
import os
os.environ.setdefault("SWARMGUARD_SKIP_DOTENV", "1")
os.environ.setdefault("OPERATOR_SECRET", "test-secret")

import pytest
from backend.app.store import MemoryStore
from backend.app.gateway import Gateway
from backend.app.detector import Detector
from simulator.seeds import setup_world, agents_for_task
from simulator import scenarios

OP = {"x-operator-secret": "test-secret"}


def world():
    s = MemoryStore()
    setup_world(s)
    return s, Gateway(s)


def agent(s, task, i=0):
    return agents_for_task(s, "demo", task)[i]


def status(s, agent_id):
    return s.find_one("agents", {"_id": agent_id, "tenant_id": "demo"})["status"]


# --------------------------------------------------------------------------
# P0 — must land before the demo. Small, contained, high credibility impact.
# --------------------------------------------------------------------------

@pytest.mark.p0
def test_p0_1_task_id_spoofing_cannot_hide_a_cross_team_bridge():
    """ATTACK: readers pass the writer's task_id, so every write->read pair looks
    same-team and R2/R3 never fire. Fix: task is ALWAYS derived server-side from
    the agent record; a mismatched caller-supplied task_id is denied or ignored
    and recorded, never trusted."""
    s, gw = world()
    qa, mk, pr = agent(s, "task_qa"), agent(s, "task_marketing"), agent(s, "task_procurement")
    w = gw.write_artifact("demo", qa["_id"], qa["task_id"], "board_alpha", "c", "hello", "a1")
    gw.read_artifact("demo", mk["_id"], "task_qa", w["artifact_id"], "a2")   # spoofed
    gw.read_artifact("demo", pr["_id"], "task_qa", w["artifact_id"], "a3")   # spoofed
    # Every stored event must carry the agent's REAL task.
    for e in s.find("events", {"tenant_id": "demo"}):
        if e["agent_id"]:
            real = s.find_one("agents", {"_id": e["agent_id"], "tenant_id": "demo"})["task_id"]
            assert e["task_id"] == real, f"event {e['_id']} stored caller-supplied task {e['task_id']}"
    eps = Detector(s).run("demo")
    assert eps, "spoofed task_id must not make a 3-team board swarm invisible"


@pytest.mark.p0
def test_p0_2_high_impact_tool_with_empty_resource_is_denied():
    """ATTACK: export_data with resource_id='' skips the resource check and EXECUTES."""
    s, gw = world()
    a = agent(s, "task_qa")
    r = gw.execute_tool("demo", a["_id"], a["task_id"], "export_data", "export", "", "e1")
    assert r["decision"] == "deny" and r["executed"] is False
    assert s.count("resource_ledger", {"tenant_id": "demo"}) == 0


@pytest.mark.p0
def test_p0_3_action_id_is_scoped_per_agent_and_cannot_be_hijacked():
    """ATTACK: agent A pre-claims an action_id; agent B's legitimate call with the
    same id silently returns A's 'deny' result and never runs (DoS + info leak)."""
    s, gw = world()
    att, vic = agent(s, "task_qa"), agent(s, "task_marketing")
    gw.execute_tool("demo", att["_id"], att["task_id"], "request_sensitive_doc", "read",
                    "sensitive_mock_dataset", "shared-id")
    r = gw.execute_tool("demo", vic["_id"], vic["task_id"], "read_resource", "read", "market_brief", "shared-id")
    assert r["decision"] == "allow" and r["executed"] is True


@pytest.mark.p0
def test_p0_4_same_action_id_with_different_request_is_a_conflict_not_a_replay():
    s, gw = world()
    a = agent(s, "task_marketing")
    gw.execute_tool("demo", a["_id"], a["task_id"], "read_resource", "read", "market_brief", "x1")
    r = gw.execute_tool("demo", a["_id"], a["task_id"], "read_resource", "read", "brand_assets", "x1")
    assert r["outcome"] == "conflict" and r["executed"] is False


@pytest.mark.p0
def test_p0_5_polling_the_detector_does_not_duplicate_episodes():
    """FAILURE: episodes are deduped by exact evidence set, so every new event on the
    same board creates ANOTHER episode. One board = one episode, extended in place."""
    s, gw = world()
    qa = agent(s, "task_qa")
    w = gw.write_artifact("demo", qa["_id"], qa["task_id"], "board_alpha", "c", "note", "d0")
    for i, (t, k) in enumerate([("task_marketing", 0), ("task_procurement", 0),
                                ("task_support", 0), ("task_marketing", 1)]):
        a = agent(s, t, k)
        gw.read_artifact("demo", a["_id"], a["task_id"], w["artifact_id"], f"d{i+1}")
        Detector(s).run("demo")
    eps = s.find("episodes", {"tenant_id": "demo"})
    assert len(eps) == 1, f"expected 1 episode for 1 board, got {len(eps)}"
    assert len(eps[0]["agent_ids"]) == 5


@pytest.mark.p0
def test_p0_6_rules_yaml_is_actually_used():
    """FAILURE: README says weights live in configs/rules.yaml; detector hardcodes them
    and ignores propagation_min_agents/min_tasks/window/threshold entirely."""
    s = MemoryStore()
    scenarios.run_s3(s)
    strict = Detector(s, rules={"propagation_min_agents": 50}).analyze("demo")
    assert all("R3_PROPAGATION" not in c["triggered_rules"] for c in strict)


@pytest.mark.p0
def test_p0_7_http_agent_routes_require_agent_credentials():
    """ATTACK: anyone on the network can POST as any agent_id. Used below to frame an
    innocent agent. Fix: per-agent key (header x-agent-key) bound to agent_id+tenant."""
    from fastapi.testclient import TestClient
    from backend.app.main import app, store
    from backend.app.identity import issue_agent_key
    c = TestClient(app)
    c.post("/api/demo/run", json={"scenario": "S0"}, headers=OP)
    body = {"agent_id": "agent_21", "tool": "read_resource", "action": "read",
            "resource_id": "support_kb", "action_id": "k1"}
    assert c.post("/api/tool/execute", json=body).status_code == 401
    wrong = issue_agent_key("demo", "agent_00")
    assert c.post("/api/tool/execute", json=body, headers={"x-agent-key": wrong}).status_code in (401, 403)
    right = issue_agent_key("demo", "agent_21")
    r = c.post("/api/tool/execute", json=body, headers={"x-agent-key": right})
    assert r.status_code == 200


@pytest.mark.p0
def test_p0_8_get_requests_never_quarantine_anyone():
    """ATTACK (works today, unauthenticated): POST two denied calls as agent_21, then a
    plain GET /api/metrics runs the detector with quarantine=True and pauses agent_21.
    Fix: GET endpoints are read-only; detection runs on the write path."""
    from fastapi.testclient import TestClient
    from backend.app.main import app, store
    c = TestClient(app)
    c.post("/api/demo/run", json={"scenario": "S0"}, headers=OP)
    before = {a["_id"]: a["status"] for a in store.find("agents", {"tenant_id": "demo"})}
    n_eps = store.count("episodes", {"tenant_id": "demo"})
    # attacker has no credentials; even so, GETs must not mutate state
    for i, tool in enumerate(["request_sensitive_doc", "export_data"]):
        c.post("/api/tool/execute", json={"agent_id": "agent_21", "tool": tool, "action": "read",
                                          "resource_id": "sensitive_mock_dataset", "action_id": f"f{i}"})
    for path in ("/api/metrics", "/api/episodes", "/api/graph"):
        c.get(path)
    after = {a["_id"]: a["status"] for a in store.find("agents", {"tenant_id": "demo"})}
    assert after == before
    assert store.count("episodes", {"tenant_id": "demo"}) == n_eps


@pytest.mark.p0
def test_p0_9_detection_runs_on_the_write_path_without_polling():
    """FAILURE: detection only happens inside /api/demo/run or a GET. Live agents
    calling the HTTP gateway are never analysed. Fix: after each authenticated
    agent POST, the API runs the (incremental or full) detector for that tenant."""
    from fastapi.testclient import TestClient
    from backend.app.main import app, store
    from backend.app.identity import issue_agent_key
    c = TestClient(app)
    c.post("/api/demo/run", json={"scenario": "S0"}, headers=OP)
    store.clear(preserve=("agents", "tasks", "policies", "verified_cases"), tenant_id="demo")
    def h(aid): return {"x-agent-key": issue_agent_key("demo", aid)}
    w = c.post("/api/artifacts/write", headers=h("agent_02"),
               json={"agent_id": "agent_02", "resource_id": "board_alpha", "content": "try it", "action_id": "w1"}).json()
    for i, aid in enumerate(["agent_00", "agent_03", "agent_04"]):
        c.post("/api/artifacts/read", headers=h(aid),
               json={"agent_id": aid, "artifact_id": w["artifact_id"], "action_id": f"r{i}"})
    c.post("/api/tool/execute", headers=h("agent_00"),
           json={"agent_id": "agent_00", "tool": "request_sensitive_doc", "action": "read",
                 "resource_id": "sensitive_mock_dataset", "action_id": "s1"})
    # NO GET, NO demo/run: the episode must already exist.
    eps = store.find("episodes", {"tenant_id": "demo"})
    assert len(eps) == 1 and eps[0]["status"] == "contained"


@pytest.mark.p0
def test_p0_10_demo_click_for_one_tenant_does_not_wipe_another():
    """FAILURE: store.clear() and BatchingStore.flush() run delete_many({}) on every
    collection, so a demo-tenant click deletes tenant2 (and any real tenant)."""
    from fastapi.testclient import TestClient
    from backend.app.main import app, store
    c = TestClient(app)
    c.post("/api/demo/run", json={"scenario": "S5"}, headers=OP)
    n_t2 = store.count("events", {"tenant_id": "tenant2"})
    assert n_t2 > 0
    c.post("/api/demo/run", json={"scenario": "S1", "tenant_id": "demo"}, headers=OP)
    assert store.count("events", {"tenant_id": "tenant2"}) == n_t2


# --------------------------------------------------------------------------
# P1 — the detection upgrades that make the "swarm" claim defensible.
# --------------------------------------------------------------------------

@pytest.mark.p1
def test_p1_1_two_agent_cross_team_channel_is_at_least_a_watch():
    """GAP: writer + 1 cross-team reader = R2 only = silently dropped. A covert channel
    between two agents is exactly the early signal the project pitch is about."""
    s, gw = world()
    qa, mk = agent(s, "task_qa"), agent(s, "task_marketing")
    w = gw.write_artifact("demo", qa["_id"], qa["task_id"], "board_alpha", "c", "step 1", "b1")
    gw.read_artifact("demo", mk["_id"], mk["task_id"], w["artifact_id"], "b2")
    eps = Detector(s).run("demo")
    assert len(eps) == 1 and eps[0]["status"] == "watch"
    assert status(s, qa["_id"]) == "active" and status(s, mk["_id"]) == "active"


@pytest.mark.p1
def test_p1_2_taint_survives_laundering_through_an_approved_channel():
    """GAP: QA -> board_alpha -> Marketing; Marketing re-posts into market_brief (which
    Support may read). Support agents now carry QA's instruction and nothing fires.
    Fix: exposure/taint lineage — an agent that read an unauthorized artifact taints
    what it writes next (within the window); readers of tainted artifacts are exposed."""
    s, gw = world()
    qa, mk = agent(s, "task_qa"), agent(s, "task_marketing")
    w = gw.write_artifact("demo", qa["_id"], qa["task_id"], "board_alpha", "c", "try sensitive_mock_dataset", "c1")
    gw.read_artifact("demo", mk["_id"], mk["task_id"], w["artifact_id"], "c2")
    w2 = gw.write_artifact("demo", mk["_id"], mk["task_id"], "market_brief", "c", "FYI: try sensitive_mock_dataset", "c3")
    sup = [agent(s, "task_support", i) for i in range(3)]
    for i, a in enumerate(sup):
        gw.read_artifact("demo", a["_id"], a["task_id"], w2["artifact_id"], f"c4{i}")
    eps = Detector(s).run("demo")
    assert eps, "laundered propagation must produce an episode"
    exposed = set().union(*[set(e.get("exposed_agent_ids", [])) for e in eps])
    assert {a["_id"] for a in sup} <= exposed


@pytest.mark.p1
def test_p1_3_graduated_containment_in_s2():
    """Containment should be proportional: the author of the unauthorized channel and the
    agent that attempted the sensitive action are quarantined; agents that only READ are
    'restricted' (keep doing normal work, high-impact tools denied)."""
    s = MemoryStore()
    info = scenarios.run_s2(s)
    Detector(s).run("demo")
    writer, drifter = info["cohort"][0], "agent_00"
    passive = [a for a in info["cohort"] if a not in (writer, drifter)]
    assert status(s, writer) == "quarantined" and status(s, drifter) == "quarantined"
    gw = Gateway(s)
    for aid in passive:
        assert status(s, aid) == "restricted"
        a = s.find_one("agents", {"_id": aid, "tenant_id": "demo"})
        own = s.find_one("tasks", {"_id": a["task_id"], "tenant_id": "demo"})["allowed_resources"][0]
        assert gw.execute_tool("demo", aid, None, "read_resource", "read", own, f"ok_{aid}")["decision"] == "allow"
        assert gw.execute_tool("demo", aid, None, "export_data", "export", own, f"hi_{aid}")["decision"] == "deny"


@pytest.mark.p1
def test_p1_4_board_content_that_points_outside_scope_is_a_signal():
    """The S2 note literally says 'try the sensitive_mock_dataset next'. Content naming a
    resource that neither the writer's nor the reader's task may use is a deterministic,
    non-LLM signal (R7_SCOPE_ESCALATION_CONTENT)."""
    s = MemoryStore()
    scenarios.run_s3(s)  # no sensitive attempt at all — content is the only tell
    eps = Detector(s).run("demo")
    assert any("R7_SCOPE_ESCALATION_CONTENT" in e["triggered_rules"] for e in eps)


@pytest.mark.p1
def test_p1_5_memory_is_not_tautological():
    """FAILURE: case_text and the query are both mostly a fixed template, so an unrelated
    single-agent telemetry lie (S4) 'matches' a confirmed board-swarm case at ~0.71."""
    from backend.app.memory import confirm_episode_as_case
    s = MemoryStore()
    scenarios.run_s2(s)
    e2 = Detector(s).run("demo")[0]
    case = confirm_episode_as_case(s, "demo", e2["_id"])
    scenarios.run_s4(s)
    e4 = Detector(s).run("demo")[0]
    assert case["_id"] not in [c["_id"] for c in e4["similar_cases"]["results"]]
    scenarios.run_s2(s)
    e2b = Detector(s).run("demo")[0]
    assert case["_id"] in [c["_id"] for c in e2b["similar_cases"]["results"]]


@pytest.mark.p1
def test_p1_6_confirm_moves_episode_lifecycle_and_records_who():
    from backend.app.memory import confirm_episode_as_case
    s = MemoryStore()
    scenarios.run_s2(s)
    ep = Detector(s).run("demo")[0]
    confirm_episode_as_case(s, "demo", ep["_id"], actor="operator:demo")
    stored = s.find_one("episodes", {"_id": ep["_id"], "tenant_id": "demo"})
    assert stored["status"] == "confirmed" and stored.get("confirmed_by") == "operator:demo"


@pytest.mark.p1
def test_p1_7_events_have_a_monotonic_sequence():
    """Ordering by ISO timestamp strings is fragile (equal ts on coarse clocks makes a read
    look like it preceded its write). Each tenant gets a monotonic integer seq."""
    s = MemoryStore()
    scenarios.run_s2(s)
    seqs = [e["seq"] for e in s.find("events", {"tenant_id": "demo"})]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


@pytest.mark.p1
def test_p1_8_single_benign_mistake_is_not_a_swarm_quarantine():
    """One agent, one denied sensitive request, no shared artifact: today this is R1+R6
    and the agent is quarantined as if it were a swarm. It should be an alert on that
    agent (blocked at the gateway already), not an automatic quarantine."""
    s, gw = world()
    a = agent(s, "task_procurement")
    gw.execute_tool("demo", a["_id"], a["task_id"], "request_sensitive_doc", "read", "sensitive_mock_dataset", "m1")
    eps = Detector(s).run("demo")
    assert status(s, a["_id"]) == "active"
    assert all(e["status"] in ("watch", "alert") for e in eps)
