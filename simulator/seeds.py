"""Seeded demo world: Northstar Labs. Deterministic IDs so replays are identical.

IDs are tenant-prefixed for non-demo tenants (task_tenant2_..., tenant2_agent_00):
MongoDB _id is unique per collection, so two tenants cannot both own a bare
'task_marketing' document. Found by running the suite against a real mongod.
"""
from __future__ import annotations

TASKS = {
    "task_marketing": {"description": "Marketing content", "allowed_resources": ["market_brief", "brand_assets"],
                       "allowed_actions": ["read", "write"], "collaborations": [{"with_task": "task_support", "resource": "market_brief"}]},
    "task_support": {"description": "Customer support", "allowed_resources": ["support_kb", "market_brief"],
                     "allowed_actions": ["read", "write"], "collaborations": [{"with_task": "task_marketing", "resource": "market_brief"}]},
    "task_qa": {"description": "Software QA", "allowed_resources": ["qa_ticket", "test_results"],
                "allowed_actions": ["read", "write"], "collaborations": []},
    "task_procurement": {"description": "Procurement", "allowed_resources": ["vendor_list"],
                         "allowed_actions": ["read", "write"], "collaborations": []},
}
TASK_ORDER = ["task_marketing", "task_support", "task_qa", "task_procurement"]
ALL_TOOLS = ["read_resource", "write_note", "request_sensitive_doc", "export_data"]

def _tid(tenant_id: str, task_id: str) -> str:
    return task_id if tenant_id == "demo" else f"{task_id}_{tenant_id}"

def _aid(tenant_id: str, i: int) -> str:
    return f"agent_{i:02d}" if tenant_id == "demo" else f"{tenant_id}_agent_{i:02d}"

def setup_world(store, tenant_id: str = "demo", n_agents: int = 30):
    store.insert("policies", {"_id": f"pol_{tenant_id}", "tenant_id": tenant_id, "version": 1,
                              "allowed_edges": [], "blocked_actions": [], "high_impact_tools": ["request_sensitive_doc"]})
    for tid, t in TASKS.items():
        full = _tid(tenant_id, tid)
        collabs = [{"with_task": _tid(tenant_id, c["with_task"]), "resource": c["resource"]}
                   for c in t["collaborations"]]
        store.insert("tasks", {"_id": full, "tenant_id": tenant_id, "description": t["description"],
                               "assigned_agents": [], "allowed_resources": t["allowed_resources"],
                               "allowed_actions": t["allowed_actions"], "collaborations": collabs,
                               "sensitivity": "internal", "expires_at": None})
    agents = []
    for i in range(n_agents):
        base_tid = TASK_ORDER[i % len(TASK_ORDER)]
        tid = _tid(tenant_id, base_tid)
        aid = _aid(tenant_id, i)
        task = TASKS[base_tid]
        agents.append(store.insert("agents", {
            "_id": aid, "tenant_id": tenant_id, "name": f"Agent {i:02d}", "task_id": tid,
            "role": base_tid.replace("task_", ""), "status": "active", "session_id": f"sess_{tenant_id}_{i:02d}",
            "approved_tools": list(ALL_TOOLS), "approved_resources": list(task["allowed_resources"]) + ["sensitive_mock_dataset"],
            "group_id": tid}))
    return agents

def agents_for_task(store, tenant_id, task_id):
    full = _tid(tenant_id, task_id)
    return [a for a in store.find("agents", {"tenant_id": tenant_id}) if a["task_id"] == full]
