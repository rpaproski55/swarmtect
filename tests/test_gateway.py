from backend.app.gateway import Gateway
from simulator.seeds import setup_world

def test_allowed_tool_executes(store):
    setup_world(store)
    gw = Gateway(store)
    r = gw.execute_tool("demo", "agent_00", "task_marketing", "read_resource", "read", "market_brief", "a1")
    assert r["decision"] == "allow" and r["executed"] is True
    assert store.count("resource_ledger", {"tenant_id": "demo"}) == 1

def test_sensitive_doc_denied_before_effect(store):
    setup_world(store)
    gw = Gateway(store)
    r = gw.execute_tool("demo", "agent_00", "task_marketing", "request_sensitive_doc", "read", "sensitive_mock_dataset", "a1")
    assert r["decision"] == "deny" and r["executed"] is False
    assert store.count("resource_ledger", {"tenant_id": "demo"}) == 0
    eff = store.find_one("gateway_effects", {"action_id": "a1"})
    assert eff["executed"] is False

def test_action_id_dedupe(store):
    setup_world(store)
    gw = Gateway(store)
    gw.execute_tool("demo", "agent_00", "task_marketing", "read_resource", "read", "market_brief", "dup1")
    r2 = gw.execute_tool("demo", "agent_00", "task_marketing", "read_resource", "read", "market_brief", "dup1")
    assert r2["outcome"] == "duplicate"
    assert store.count("resource_ledger", {"tenant_id": "demo"}) == 1

def test_quarantined_agent_blocked_others_continue(store):
    setup_world(store)
    gw = Gateway(store)
    gw.quarantine("demo", "agent_00")
    r = gw.execute_tool("demo", "agent_00", "task_marketing", "read_resource", "read", "market_brief", "q1")
    assert r["decision"] == "deny"
    r2 = gw.execute_tool("demo", "agent_01", "task_support", "read_resource", "read", "support_kb", "q2")
    assert r2["decision"] == "allow"
