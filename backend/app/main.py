from __future__ import annotations
import os
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .store import get_store
from .gateway import Gateway
from .detector import Detector, baseline_detect
from .metrics import compute_metrics

app = FastAPI(title="SwarmGuard", version="0.1.0")
store = get_store()
OPERATOR_SECRET = os.environ.get("OPERATOR_SECRET", "demo-operator-secret-change-me")

import threading, logging, traceback
log = logging.getLogger("swarmguard")
# Demo runs wipe and rewrite the shared demo collections, and scenario action IDs restart at 1,
# so two overlapping runs (double click, a second tab, a script) would collide on the unique
# (tenant_id, action_id) index. Detector re-runs triggered by GETs also write. Serialize them.
DEMO_LOCK = threading.RLock()

def _fail(where: str, e: Exception):
    log.error("%s failed: %s\n%s", where, e, traceback.format_exc())
    name = type(e).__name__
    hint = ""
    if "ServerSelection" in name or "AutoReconnect" in name or "NetworkTimeout" in name:
        hint = " (Atlas unreachable: check Wi-Fi and the Atlas IP access list)"
    elif "BulkWrite" in name or "DuplicateKey" in name:
        hint = " (overlapping demo runs; try again)"
    raise HTTPException(500, f"{where}: {name}: {str(e)[:300]}{hint}")

def gw() -> Gateway:
    return Gateway(store)

def require_operator(x_operator_secret: str | None):
    if x_operator_secret != OPERATOR_SECRET:
        raise HTTPException(403, "operator auth required")

class ToolReq(BaseModel):
    tenant_id: str = "demo"; agent_id: str; task_id: str | None = None; tool: str; action: str
    resource_id: str = Field(min_length=1); artifact_id: str | None = None; payload: dict | None = None; action_id: str
class WriteReq(BaseModel):
    tenant_id: str = "demo"; agent_id: str; task_id: str | None = None; resource_id: str
    channel_id: str = "chan"; content: str; action_id: str
class ReadReq(BaseModel):
    tenant_id: str = "demo"; agent_id: str; task_id: str | None = None; artifact_id: str; action_id: str
class DemoReq(BaseModel):
    scenario: str = "S2"; tenant_id: str = "demo"

def _page(name: str):
    from fastapi.responses import HTMLResponse
    import pathlib
    return HTMLResponse(pathlib.Path(__file__).parent.joinpath("static", name).read_text())

@app.get("/")
def story():
    """Guided demo: approved teamwork -> unapproved swarm blocked -> case memory."""
    return _page("story.html")

@app.get("/classic")
def cockpit():
    """Technical cockpit: counters, evidence graph, raw event stream."""
    return _page("cockpit.html")

@app.get("/api/world")
def world(tenant_id: str = "demo"):
    """Teams (tasks), what each may use, and which cross-team sharing is approved."""
    return {"tasks": store.find("tasks", {"tenant_id": tenant_id})}

@app.get("/api/events")
def events_list(tenant_id: str = "demo"):
    """Stored gateway events for the tenant, oldest first (single read, no detector run)."""
    return sorted(store.find("events", {"tenant_id": tenant_id}), key=lambda e: e["ts"])

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
            ev = store.find_one("events", {"_id": eid, "tenant_id": tenant_id})
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
    with DEMO_LOCK:
        case = confirm_episode_as_case(store, tenant_id, episode_id)
    if not case:
        raise HTTPException(404, "episode not found")
    return case

@app.get("/api/cases/search")
def cases_search(q: str, tenant_id: str = "demo"):
    from .memory import search_cases, search_cases_local_embedding
    if getattr(store, "backend", "") == "mongodb-atlas":
        return search_cases(store, tenant_id, q)
    return search_cases_local_embedding(store, tenant_id, q)

@app.get("/api/health")
def health():
    backend = getattr(store, "backend", "unknown")
    if backend != "mongodb-atlas":
        return {"ok": True, "store_backend": backend, "atlas_connected": False}
    try:
        store.client.admin.command("ping")  # real round trip, not just "configured for Atlas"
        return {"ok": True, "store_backend": backend, "atlas_connected": True}
    except Exception as e:
        return {"ok": False, "store_backend": backend, "atlas_connected": False, "error": type(e).__name__}

def _require_agent(req, key: str | None):
    """401 without a key; 403 if the key isn't valid for (tenant_id, agent_id) in the body."""
    from .identity import verify_agent_key
    if not key:
        raise HTTPException(401, "agent credentials required (x-agent-key)")
    if not verify_agent_key(req.tenant_id, req.agent_id, key):
        raise HTTPException(403, "x-agent-key is not valid for this agent")


def _detect_after_write(tenant_id: str):
    """Detection on the write path: runs after the agent's response is sent (BackgroundTasks),
    serialized with demo runs. Synchronous post-event detection; a Change Streams worker is future work."""
    try:
        with DEMO_LOCK:
            Detector(store).run(tenant_id)
    except Exception as e:  # never fail the agent's call because of detection
        log.error("post-write detection failed: %s", e)


@app.post("/api/tool/execute")
def tool_execute(req: ToolReq, background: BackgroundTasks, x_agent_key: str | None = Header(default=None)):
    _require_agent(req, x_agent_key)
    with DEMO_LOCK:
        r = gw().execute_tool(req.tenant_id, req.agent_id, req.task_id, req.tool, req.action,
                              req.resource_id, req.action_id, req.payload)
    background.add_task(_detect_after_write, req.tenant_id)
    return r

@app.post("/api/artifacts/write")
def artifact_write(req: WriteReq, background: BackgroundTasks, x_agent_key: str | None = Header(default=None)):
    _require_agent(req, x_agent_key)
    with DEMO_LOCK:
        r = gw().write_artifact(req.tenant_id, req.agent_id, req.task_id, req.resource_id,
                                req.channel_id, req.content, req.action_id)
    background.add_task(_detect_after_write, req.tenant_id)
    return r

@app.post("/api/artifacts/read")
def artifact_read(req: ReadReq, background: BackgroundTasks, x_agent_key: str | None = Header(default=None)):
    _require_agent(req, x_agent_key)
    with DEMO_LOCK:
        r = gw().read_artifact(req.tenant_id, req.agent_id, req.task_id, req.artifact_id, req.action_id)
    background.add_task(_detect_after_write, req.tenant_id)
    return r

@app.get("/api/demo/agent-keys")
def demo_agent_keys(tenant_id: str = "demo", x_operator_secret: str | None = Header(default=None)):
    """Operator only: keys for the demo tenant so a judge can drive a live agent with curl."""
    require_operator(x_operator_secret)
    from .identity import issue_agent_key
    return {a["_id"]: issue_agent_key(tenant_id, a["_id"]) for a in store.find("agents", {"tenant_id": tenant_id})}

@app.get("/api/agents")
def agents(tenant_id: str = "demo"):
    return store.find("agents", {"tenant_id": tenant_id})

@app.get("/api/episodes")
def episodes(tenant_id: str = "demo"):
    """Read-only: detection runs on the write path and in /api/demo/run, never on GET."""
    return store.find("episodes", {"tenant_id": tenant_id})

@app.get("/api/episodes/{episode_id}")
def episode(episode_id: str, tenant_id: str = "demo"):
    ep = store.find_one("episodes", {"_id": episode_id, "tenant_id": tenant_id})
    if not ep:
        raise HTTPException(404, "episode not found")
    ids = ep["evidence_event_ids"]
    by_id = {e["_id"]: e for e in store.find("events", {"tenant_id": tenant_id, "_id": {"$in": ids}})}  # one round trip
    artifacts = store.find("artifacts", {"tenant_id": tenant_id, "_id": {"$in": ep.get("artifact_ids", [])}}) if ep.get("artifact_ids") else []
    effects = store.find("gateway_effects", {"tenant_id": tenant_id, "event_id": {"$in": ids}})
    return {**ep, "timeline": sorted([by_id[i] for i in ids if i in by_id], key=lambda e: e["ts"]),
            "artifacts": artifacts, "effects": effects}

@app.get("/api/metrics")
def metrics(tenant_id: str = "demo"):
    """Read-only."""
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
    with DEMO_LOCK:
        if os.environ.get("ALLOW_GLOBAL_RESET") == "1":
            store.clear(preserve=("verified_cases",))
            return {"reset": True, "scope": "all tenants"}
        for t in ("demo", "tenant2", "redteam"):
            store.clear(preserve=("verified_cases",), tenant_id=t)
    return {"reset": True, "scope": "demo tenants only"}

@app.post("/api/demo/run")
def demo_run(req: DemoReq, x_operator_secret: str | None = Header(default=None)):
    require_operator(x_operator_secret)
    from simulator.scenarios import SCENARIOS
    if req.scenario != "S6" and req.scenario not in SCENARIOS:
        raise HTTPException(400, f"unknown scenario {req.scenario}")
    try:
        with DEMO_LOCK:
            return _demo_run(req)
    except HTTPException:
        raise
    except Exception as e:
        _fail(f"demo run {req.scenario}", e)

def _demo_run(req: "DemoReq"):
    from simulator.scenarios import SCENARIOS
    import time as _t
    t0 = _t.perf_counter()
    # On Atlas, run the click's workload in a write-behind batch, then persist in bulk (see BatchingStore).
    from .store import BatchingStore
    run_store = BatchingStore(store) if getattr(store, "backend", "") == "mongodb-atlas" else store
    extra = {}
    if req.scenario == "S6":
        from simulator.langgraph_agents import run_s6_langgraph
        info = run_s6_langgraph(run_store, tenant_id=req.tenant_id)
        extra["langgraph_agents"] = info.get("langgraph_agents")
    else:
        info = SCENARIOS[req.scenario](run_store, tenant_id=req.tenant_id)
    eps = Detector(run_store).run(req.tenant_id)
    if run_store is not store:
        extra["persisted"] = run_store.flush()
    extra["elapsed_ms"] = round((_t.perf_counter() - t0) * 1000)
    return {"scenario": req.scenario, "truth_episodes": info.get("truth_episodes"),
            "episodes_detected": len(eps), "episodes": eps, "metrics": compute_metrics(store, req.tenant_id), **extra}
