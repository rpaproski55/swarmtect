import pytest
pytest.importorskip("langgraph")
from backend.agent_engine.main import build_monitored_agent
from simulator.seeds import setup_world

def test_langgraph_agent_calls_through_gateway(store):
    setup_world(store)
    agent = build_monitored_agent(store)
    assert agent is not None
    out = agent.invoke({"request": {"agent_id": "agent_00", "task_id": "task_marketing",
                                    "tool": "read_resource", "action": "read",
                                    "resource_id": "market_brief", "action_id": "lg_ok"}})
    assert out["result"]["decision"] == "allow" and out["result"]["executed"] is True
    out2 = agent.invoke({"request": {"agent_id": "agent_00", "task_id": "task_marketing",
                                     "tool": "request_sensitive_doc", "action": "read",
                                     "resource_id": "sensitive_mock_dataset", "action_id": "lg_denied"}})
    assert out2["result"]["decision"] == "deny" and out2["result"]["executed"] is False
    assert store.count("resource_ledger", {"resource_id": "sensitive_mock_dataset"}) == 0
