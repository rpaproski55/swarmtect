from __future__ import annotations

HIGH_IMPACT = {"request_sensitive_doc", "export_data", "grant_access"}

def is_authorized(store, tenant_id: str, agent: dict, task: dict | None,
                  tool: str | None, resource_id: str | None) -> tuple[bool, str]:
    """Policy-relative check. Returns (allowed, reason)."""
    if agent.get("status") in ("quarantined", "paused"):
        return False, f"agent {agent['_id']} is {agent['status']}"
    if task is None:
        return False, "unknown task"
    if tool and tool not in (agent.get("approved_tools") or []):
        # artifact read/write tools are handled separately; tool tools must be approved
        if tool not in ("read_resource", "write_note"):
            return False, f"tool {tool} not in agent approved_tools"
    if resource_id and resource_id not in (task.get("allowed_resources") or []):
        return False, f"resource {resource_id} not in task {task['_id']} allowed_resources"
    if resource_id and (agent.get("approved_resources") or []) and resource_id not in agent["approved_resources"]:
        return False, f"resource {resource_id} not in agent approved_resources"
    return True, "authorized"

def collaboration_approved(store, tenant_id: str, task_a: str, task_b: str, resource_id: str) -> bool:
    """True if a task lists the other task in collaborations AND the resource is allowed for both,
    or a policy allowed_edge covers it."""
    if task_a == task_b:
        return True
    for tid in (task_a, task_b):
        t = store.find_one("tasks", {"_id": tid, "tenant_id": tenant_id})
        if not t:
            continue
        for c in t.get("collaborations") or []:
            if c.get("with_task") in (task_a, task_b) and c.get("resource") == resource_id:
                return True
    pol = store.find_one("policies", {"tenant_id": tenant_id})
    if pol:
        for e in pol.get("allowed_edges") or []:
            if {e.get("task_from"), e.get("task_to")} == {task_a, task_b} and e.get("resource") == resource_id:
                return True
    return False
