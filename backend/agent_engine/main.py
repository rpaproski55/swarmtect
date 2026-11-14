"""Atlas Agent Engine / LangGraph integration — REAL when the SDKs are installed.

Status (honest): `agent-engine-sdk-langgraph` and `langgraph` are optional deps.
If they are not installed / no preview access, importing this module reports that
exactly instead of pretending to be deployed. The monitored agent below, when
langgraph IS available, makes its tool calls THROUGH the SwarmGuard gateway —
that is the integration point that matters for detection.
"""
from __future__ import annotations

def agent_engine_status() -> dict:
    try:
        import agent_engine_sdk_langgraph  # noqa: F401
        sdk = True
    except Exception:
        sdk = False
    try:
        import langgraph  # noqa: F401
        lg = True
    except Exception:
        lg = False
    return {"agent_engine_sdk_installed": sdk, "langgraph_installed": lg,
            "deployed": False,
            "note": "Deployment requires Atlas Agent Engine preview access + `agentengine` CLI auth; "
                    "not claimed until the CLI confirms it. See STATUS.md."}

def build_monitored_agent(store, tenant_id: str = "demo"):
    """A minimal LangGraph agent whose single tool is gateway-mediated. Returns None if langgraph absent."""
    try:
        from langgraph.graph import StateGraph, END
    except Exception:
        return None
    from backend.app.gateway import Gateway
    gw = Gateway(store)

    def act(state):
        req = state["request"]
        op = req.get("op", "tool")
        if op == "write_artifact":
            result = gw.write_artifact(tenant_id, req["agent_id"], req.get("task_id"), req["resource_id"],
                                       req.get("channel_id", "chan"), req.get("content", ""), req["action_id"])
        elif op == "read_artifact":
            result = gw.read_artifact(tenant_id, req["agent_id"], req.get("task_id"), req["artifact_id"], req["action_id"])
        else:
            result = gw.execute_tool(tenant_id, req["agent_id"], req.get("task_id"), req["tool"],
                                     req["action"], req["resource_id"], req["action_id"])
        return {"result": result}
    g = StateGraph(dict)
    g.add_node("act", act)
    g.set_entry_point("act")
    g.add_edge("act", END)
    return g.compile()
