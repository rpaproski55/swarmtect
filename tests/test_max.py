import os
os.environ.setdefault("OPERATOR_SECRET", "test-secret")
import pytest
from fastapi.testclient import TestClient

def test_verified_case_memory_loop(store):
    """Episode -> operator confirms -> verified case -> NEXT episode cites it as similar."""
    from simulator import scenarios
    from backend.app.detector import Detector
    from backend.app.memory import confirm_episode_as_case, search_cases_local_embedding
    scenarios.run_s2(store)
    eps = Detector(store).run("demo")
    assert eps and not eps[0].get("similar_cases", {}).get("results")
    case = confirm_episode_as_case(store, "demo", eps[0]["_id"])
    assert case and case["review_status"] == "verified"
    hits = search_cases_local_embedding(store, "demo", "unauthorized board propagation R2 R3 high impact denied")
    assert hits["results"] and hits["results"][0]["provenance_episode_id"] == eps[0]["_id"]
    assert "NOT_atlas" in hits["mode"]  # fallback is honestly labelled
    # fresh identical attack: new episode must surface the confirmed case
    scenarios.run_s2(store)
    eps2 = Detector(store).run("demo")
    assert eps2[0]["similar_cases"]["results"], "new episode should retrieve the verified case"
    # cross-tenant: tenant2 search must not see demo's case
    hits_t2 = search_cases_local_embedding(store, "tenant2", "unauthorized board propagation")
    assert hits_t2["results"] == []

def test_s6_four_real_langgraph_agents(store):
    pytest.importorskip("langgraph")
    from simulator.langgraph_agents import run_s6_langgraph
    from backend.app.detector import Detector
    info = run_s6_langgraph(store)
    if info.get("skipped"):
        pytest.skip(info["skipped"])
    assert info["langgraph_agents"] == 4
    assert info["sensitive_result"]["decision"] == "deny" and info["sensitive_result"]["executed"] is False
    eps = Detector(store).run("demo")
    assert len(eps) == 1
    assert set(info["truth_agents"]) <= set(eps[0]["agent_ids"])

def test_cockpit_graph_and_stream():
    from backend.app.main import app, store as api_store
    client = TestClient(app)
    html = client.get("/")
    assert html.status_code == 200 and "SwarmGuard" in html.text
    api_store.clear()
    r = client.post("/api/demo/run", json={"scenario": "S2"}, headers={"x-operator-secret": "test-secret"})
    assert r.status_code == 200
    g = client.get("/api/graph").json()
    assert any(n["kind"] == "episode" for n in g["nodes"])
    assert any(e["kind"] == "artifact_write" for e in g["edges"])
    # confirm endpoint requires operator auth and then works
    ep_id = r.json()["episodes"][0]["_id"]
    assert client.post(f"/api/episodes/{ep_id}/confirm").status_code == 403
    c = client.post(f"/api/episodes/{ep_id}/confirm", headers={"x-operator-secret": "test-secret"})
    assert c.status_code == 200 and c.json()["review_status"] == "verified"
    s = client.get("/api/cases/search", params={"q": "unauthorized board propagation"}).json()
    assert s["results"]
