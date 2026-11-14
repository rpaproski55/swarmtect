import os
import pytest
pytest.importorskip("agent_engine_sdk_langgraph")

def test_agent_engine_app_constructs(monkeypatch):
    monkeypatch.setenv("RUNNER_MODE", "aer")
    from backend.agent_engine.app import build_app, gateway_tool
    from simulator.seeds import setup_world
    from backend.app.store import MemoryStore
    # gateway tool logic is the same enforcement path (verified against a fresh world)
    import backend.agent_engine.app as ae
    store = MemoryStore(); setup_world(store)
    from backend.app.gateway import Gateway
    ae._gw = Gateway(store)
    r = gateway_tool("agent_00", "task_marketing", "request_sensitive_doc", "read", "sensitive_mock_dataset", "ae1")
    assert r["decision"] == "deny" and r["executed"] is False
    app = build_app()
    assert app is not None
    defs = app.get_tool_definitions()
    assert defs, "Agent Engine app must expose its gateway tool"
