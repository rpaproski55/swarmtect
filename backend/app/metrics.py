from __future__ import annotations

def compute_metrics(store, tenant_id: str = "demo") -> dict:
    events = store.find("events", {"tenant_id": tenant_id})
    effects = store.find("gateway_effects", {"tenant_id": tenant_id})
    eps = store.find("episodes", {"tenant_id": tenant_id})
    return {
        "tenant_id": tenant_id,
        "store_backend": getattr(store, "backend", "unknown"),
        "events_processed": len(events),
        "tool_attempts": len([e for e in effects]),
        "blocked_before_effect": len([e for e in effects if e["decision"] == "deny" and not e["executed"]]),
        "allowed_effects": len([e for e in effects if e["executed"]]),
        "episodes_detected": len(eps),
        "agents_quarantined": store.count("agents", {"tenant_id": tenant_id, "status": "quarantined"}),
        "episodes": [{"_id": e["_id"], "rules": e["triggered_rules"], "risk_score": e["risk_score"],
                      "agents": e["agent_ids"], "status": e["status"]} for e in eps],
    }
