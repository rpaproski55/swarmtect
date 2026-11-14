"""Real Atlas Agent Engine entrypoint, built on the official SDK
(agent-engine-sdk-langgraph 0.11.14, verified installed 2026-11-14).

Local verification: App constructs with RUNNER_MODE=aer and no Atlas URI
(tracing warns it has no destination — honest, not hidden).
Cloud deployment is NOT claimed: it requires Atlas Agent Engine preview org
access + `agentengine` CLI auth + a real MONGODB_URI. See STATUS.md.

The agent's only tool routes through the SwarmGuard gateway, so Agent Engine
agents get the same pre-action blocking as every other agent.
"""
from __future__ import annotations
import os

from backend.app.store import get_store
from backend.app.gateway import Gateway

_store = get_store()
_gw = Gateway(_store)
TENANT = os.environ.get("SWARMGUARD_TENANT", "demo")

def gateway_tool(agent_id: str, task_id: str, tool: str, action: str, resource_id: str, action_id: str) -> dict:
    """Plain function (unit-testable without the runtime)."""
    return _gw.execute_tool(TENANT, agent_id, task_id, tool, action, resource_id, action_id)

def build_app():
    """Construct the Agent Engine App and register tool + entrypoint."""
    os.environ.setdefault("RUNNER_MODE", "aer")
    from agent_engine_sdk_langgraph import App
    app = App(app_name="swarmguard-monitored-agent",
              mongodb_uri=os.environ.get("MONGODB_URI") or None,
              database_name=os.environ.get("MONGODB_DB", "swarmguard"))

    @app.tool()
    def swarmguard_execute(agent_id: str, task_id: str, tool: str, action: str,
                           resource_id: str, action_id: str) -> dict:
        """Execute a tool call through the SwarmGuard trusted gateway (blocked before effect if unauthorized)."""
        return gateway_tool(agent_id, task_id, tool, action, resource_id, action_id)

    @app.entrypoint
    def monitored_agent():
        # 'global' load strategy: entrypoint is a no-arg factory returning the runnable graph.
        from backend.agent_engine.main import build_monitored_agent
        return build_monitored_agent(_store, TENANT)

    return app

if __name__ == "__main__":
    application = build_app()
    print("Agent Engine App constructed:", type(application).__name__)
    print("Tools:", application.get_tool_definitions() if hasattr(application, "get_tool_definitions") else "n/a")
