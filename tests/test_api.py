import os
os.environ.setdefault("OPERATOR_SECRET", "test-secret")
from fastapi.testclient import TestClient
from backend.app.main import app, store

client = TestClient(app)
H = {"x-operator-secret": "test-secret"}

def test_health_and_demo_flow():
    assert client.get("/api/health").json()["ok"] is True
    store.clear()
    r = client.post("/api/demo/run", json={"scenario": "S1"}, headers=H)
    assert r.status_code == 200 and r.json()["episodes_detected"] == 0
    store.clear()
    r = client.post("/api/demo/run", json={"scenario": "S2"}, headers=H)
    body = r.json()
    assert body["episodes_detected"] == 1
    ep_id = body["episodes"][0]["_id"]
    detail = client.get(f"/api/episodes/{ep_id}").json()
    assert detail["timeline"], "episode detail must reconstruct a timeline from stored events"
    m = client.get("/api/metrics").json()
    assert m["blocked_before_effect"] >= 1
    # operator auth is enforced
    assert client.post("/api/demo/run", json={"scenario": "S2"}).status_code == 403
