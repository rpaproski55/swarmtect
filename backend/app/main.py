from __future__ import annotations
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from .store import get_store
from .gateway import Gateway
from .detector import Detector, baseline_detect
from .metrics import compute_metrics

app = FastAPI(title="SwarmGuard", version="0.1.0")
store = get_store()
OPERATOR_SECRET = os.environ.get("OPERATOR_SECRET", "demo-operator-secret-change-me")

def gw() -> Gateway:
    return Gateway(store)

def require_operator(x_operator_secret: str | None):
    if x_operator_secret != OPERATOR_SECRET:
        raise HTTPException(403, "operator auth required")

class ToolReq(BaseModel):
    tenant_id: str = "demo"; agent_id: str; task_id: str | None = None; tool: str; action: str
    resource_id: str; artifact_id: str | None = None; payload: dict | None = None; action_id: str
class WriteReq(BaseModel):
    tenant_id: str = "demo"; agent_id: str; task_id: str | None = None; resource_id: str
    channel_id: str = "chan"; content: str; action_id: str
class ReadReq(BaseModel):
    tenant_id: str = "demo"; agent_id: str; task_id: str | None = None; artifact_id: str; action_id: str
class DemoReq(BaseModel):
    scenario: str = "S2"; tenant_id: str = "demo"

@app.get("/")
def cockpit():
    from fastapi.responses import HTMLResponse
    import pathlib
    html = pathlib.Path(__file__).parent.joinpath("static", "cockpit.html").read_text()
    return HTMLResponse(html)

@app.get("/api/graph")
def graph(tenant_id: str = "demo"):
    """Graph view derived ONLY from stored episodes/events — every edge traces to an event."""
    eps = store.find("episodes", {"tenant_id": tenant_id})
    nodes, edges = {}, []
    for ep in eps:
        nodes[ep["_id"]] = {"id": ep["_id"], "kind": "episode", "label": ep["_id"]}
        for aid in ep["agent_ids"]:
            nodes[aid] = {"id": aid, "kind": "agent", "label": aid}
            edges.append({"from": aid, "to": ep["_id"], "kind": "in_episode"})
        for art in ep["artifact_ids"]:
            nodes[art] = {"id": art, "kind": "artifact", "label": art}
            edges.append({"from": art, "to": ep["_id"], "kind": "evidence_artifact"})
        for eid in ep["evidence_event_ids"]:
            ev = store.find_one("events", {"_id": eid})
            if ev and ev["event_type"] in ("artifact_write", "artifact_read") and ev.get("artifact_id"):
                edges.append({"from": ev["agent_id"], "to": ev["artifact_id"],
                              "kind": ev["event_type"], "event_id": eid})
    return {"nodes": list(nodes.values()), "edges": edges}

@app.get("/api/events/stream")
def events_stream(tenant_id: str = "demo"):
    """SSE via 1s polling of the store. Polling is the labelled fallback —
    Change Streams would replace the poll loop with Atlas provisioned, and
    blocking NEVER depends on this stream (gateway is synchronous)."""
    from fastapi.responses import StreamingResponse
    import json, time
    def gen():
        seen = set()
        for _ in range(30):  # bounded for demo; clients reconnect
            for e in store.find("events", {"tenant_id": tenant_id}):
                if e["_id"] not in seen:
                    seen.add(e["_id"])
                    yield f"data: {json.dumps(e, default=str)}\n\n"
            time.sleep(1)
    return StreamingResponse(gen(), media_type="text/event-stream")

@app.post("/api/episodes/{episode_id}/confirm")
def confirm_episode(episode_id: str, tenant_id: str = "demo", x_operator_secret: str | None = Header(default=None)):
    require_operator(x_operator_secret)
    from .memory import confirm_episode_as_case
    case = confirm_episode_as_case(store, tenant_id, episode_id)
    if not case:
        raise HTTPException(404, "episode not found")
    return case

@app.get("/api/cases/search")
def cases_search(q: str, tenant_id: str = "demo"):
    from .memory import search_cases_local_embedding
    return search_cases_local_embedding(store, tenant_id, q)

@app.get("/api/health")
def health():
    return {"ok": True, "store_backend": getattr(store, "backend", "unknown"),
            "atlas_connected": getattr(store, "backend", "") == "mongodb-atlas"}

@app.post("/api/tool/execute")
def tool_execute(req: ToolReq):
    return gw().execute_tool(req.tenant_id, req.agent_id, req.task_id, req.tool, req.action,
                             req.resource_id, req.action_id, req.payload)

@app.post("/api/artifacts/write")
def artifact_write(req: WriteReq):
    return gw().write_artifact(req.tenant_id, req.agent_id, req.task_id, req.resource_id,
                               req.channel_id, req.content, req.action_id)

@app.post("/api/artifacts/read")
def artifact_read(req: ReadReq):
    return gw().read_artifact(req.tenant_id, req.agent_id, req.task_id, req.artifact_id, req.action_id)

@app.get("/api/agents")
def agents(tenant_id: str = "demo"):
    return store.find("agents", {"tenant_id": tenant_id})

@app.get("/api/episodes")
def episodes(tenant_id: str = "demo"):
    Detector(store).run(tenant_id)
    return store.find("episodes", {"tenant_id": tenant_id})

@app.get("/api/episodes/{episode_id}")
def episode(episode_id: str, tenant_id: str = "demo"):
    ep = store.find_one("episodes", {"_id": episode_id, "tenant_id": tenant_id})
    if not ep:
        raise HTTPException(404, "episode not found")
    timeline = [store.find_one("events", {"_id": eid}) for eid in ep["evidence_event_ids"]]
    return {**ep, "timeline": [t for t in timeline if t]}

@app.get("/api/metrics")
def metrics(tenant_id: str = "demo"):
    Detector(store).run(tenant_id)
    return compute_metrics(store, tenant_id)

@app.get("/api/baseline")
def baseline(tenant_id: str = "demo"):
    return baseline_detect(store, tenant_id)

@app.post("/api/controls/{agent_id}/quarantine")
def quarantine(agent_id: str, tenant_id: str = "demo", x_operator_secret: str | None = Header(default=None)):
    require_operator(x_operator_secret)
    act = gw().quarantine(tenant_id, agent_id)
    if not act: raise HTTPException(404, "agent not found")
    return act

@app.post("/api/controls/{agent_id}/release")
def release(agent_id: str, tenant_id: str = "demo", x_operator_secret: str | None = Header(default=None)):
    require_operator(x_operator_secret)
    return gw().release(tenant_id, agent_id)

@app.post("/api/demo/reset")
def demo_reset(x_operator_secret: str | None = Header(default=None)):
    require_operator(x_operator_secret)
    store.clear()
    return {"reset": True}

@app.post("/api/demo/run")
def demo_run(req: DemoReq, x_operator_secret: str | None = Header(default=None)):
    require_operator(x_operator_secret)
    from simulator.scenarios import SCENARIOS
    if req.scenario == "S6":
        from simulator.langgraph_agents import run_s6_langgraph
        info = run_s6_langgraph(store, tenant_id=req.tenant_id)
        eps = Detector(store).run(req.tenant_id)
        return {"scenario": "S6", "truth_episodes": info.get("truth_episodes"),
                "episodes_detected": len(eps), "episodes": eps, "metrics": compute_metrics(store, req.tenant_id),
                "langgraph_agents": info.get("langgraph_agents")}
    if req.scenario not in SCENARIOS:
        raise HTTPException(400, f"unknown scenario {req.scenario}")
    info = SCENARIOS[req.scenario](store, tenant_id=req.tenant_id)
    eps = Detector(store).run(req.tenant_id)
    return {"scenario": req.scenario, "truth_episodes": info.get("truth_episodes"),
            "episodes_detected": len(eps), "episodes": eps, "metrics": compute_metrics(store, req.tenant_id)}
