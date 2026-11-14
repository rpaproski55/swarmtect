"""Trusted instrumented tool gateway — the enforcement truth source.

Blocking happens BEFORE any simulator side effect for tool execution.
Artifact write/read are observed shared-memory operations: they are recorded
authoritatively whether authorized or not (that record is the detection signal),
but they never grant a high-impact effect.
"""
from __future__ import annotations
from .models import now, new_id, digest
from .policies import is_authorized, HIGH_IMPACT

class Gateway:
    def __init__(self, store):
        self.store = store

    # -- internal helpers -------------------------------------------------
    def _agent_task(self, tenant_id, agent_id, task_id):
        """Identity is server-derived: the task is ALWAYS the agent's assigned task.
        A caller-supplied task_id is only compared, never trusted. Returns
        (agent, task, claimed_task_id_if_it_mismatched_else_None)."""
        agent = self.store.find_one("agents", {"_id": agent_id, "tenant_id": tenant_id})
        if agent is None:
            return None, None, None
        task = self.store.find_one("tasks", {"_id": agent.get("task_id"), "tenant_id": tenant_id})
        claimed = task_id if (task_id and task_id != agent.get("task_id")) else None
        return agent, task, claimed

    @staticmethod
    def _fingerprint(*parts) -> str:
        import json
        return digest("|".join(json.dumps(p, sort_keys=True, default=str) for p in parts))

    def _event(self, tenant_id, agent, task, event_type, tool, action, resource_id,
               artifact_id, outcome, metadata=None, source="gateway"):
        ev = {
            "_id": new_id("evt"), "tenant_id": tenant_id, "ts": now().isoformat(),
            "source": source, "integrity": "authoritative" if source == "gateway" else "self_reported",
            "agent_id": agent["_id"] if agent else None,
            "task_id": task["_id"] if task else (agent.get("task_id") if agent else None),
            "session_id": agent.get("session_id") if agent else None,
            "trace_id": (metadata or {}).get("trace_id"),
            "event_type": event_type, "tool": tool, "action": action,
            "resource_id": resource_id, "artifact_id": artifact_id,
            "origin_event_id": (metadata or {}).get("origin_event_id"),
            "metadata": {k: v for k, v in (metadata or {}).items()
                         if k != "simulator_truth_label"},  # truth never enters detector-visible events
            "outcome": outcome,
        }
        return self.store.insert("events", ev)

    def _dedupe(self, tenant_id, agent_id, action_id):
        # Scoped per agent: one agent can never pre-claim another agent's action_id.
        return self.store.find_one("gateway_effects", {"tenant_id": tenant_id, "agent_id": agent_id, "action_id": action_id})

    def _replay_or_conflict(self, existing, fingerprint, tenant_id, agent_id, kind, resource_id):
        """Same (agent, action_id) seen before: identical request -> idempotent replay;
        different request -> conflict, nothing executes, and the attempt is recorded."""
        if existing.get("request_fingerprint", fingerprint) == fingerprint:
            return {"decision": existing["decision"], "outcome": "duplicate", "event_id": existing["event_id"],
                    "effect_id": existing["_id"], "artifact_id": existing.get("artifact_id"),
                    "reason": "action_id already processed", "executed": existing["executed"]}
        agent = self.store.find_one("agents", {"_id": agent_id, "tenant_id": tenant_id})
        ev = self._event(tenant_id, agent, None, kind, None, "conflict", resource_id, None, "conflict",
                         {"conflicting_action_id": existing.get("action_id"), "original_effect_id": existing["_id"]})
        return {"decision": "deny", "outcome": "conflict", "event_id": ev["_id"], "effect_id": None,
                "reason": "action_id reused with a different request", "executed": False}

    # -- tool execution (blocked before effect) ---------------------------
    def execute_tool(self, tenant_id, agent_id, task_id, tool, action, resource_id, action_id, payload=None):
        fp = self._fingerprint("tool", tool, action, resource_id, payload)
        existing = self._dedupe(tenant_id, agent_id, action_id)
        if existing:
            return self._replay_or_conflict(existing, fp, tenant_id, agent_id, "tool_call", resource_id)
        agent, task, claimed = self._agent_task(tenant_id, agent_id, task_id)
        if agent is None:
            ev = self._event(tenant_id, None, task, "tool_call", tool, action, resource_id, None, "denied")
            eff = self.store.insert("gateway_effects", {
                "_id": new_id("eff"), "tenant_id": tenant_id, "event_id": ev["_id"], "action_id": action_id,
                "agent_id": agent_id, "resource_id": resource_id, "request_digest": digest(str(payload or "")), "request_fingerprint": fp,
                "decision": "deny", "executed": False, "result": None, "verified_at": now().isoformat()})
            return {"decision": "deny", "outcome": "denied", "event_id": ev["_id"], "effect_id": eff["_id"],
                    "reason": "unknown agent", "executed": False}
        high = tool in HIGH_IMPACT
        meta = {"high_impact": high}
        if not resource_id:
            allowed, reason = False, "resource_id required"
        elif claimed:
            allowed, reason = False, "claimed task does not match agent's assigned task"
            meta.update(identity_mismatch=True, claimed_task_id=claimed)
        else:
            allowed, reason = is_authorized(self.store, tenant_id, agent, task, tool, resource_id)
        if not allowed:
            ev = self._event(tenant_id, agent, task, "tool_call", tool, action, resource_id, None, "denied",
                             {**meta, "policy_reason": reason})
            eff = self.store.insert("gateway_effects", {
                "_id": new_id("eff"), "tenant_id": tenant_id, "event_id": ev["_id"], "action_id": action_id,
                "agent_id": agent_id, "resource_id": resource_id, "request_digest": digest(str(payload or "")), "request_fingerprint": fp,
                "decision": "deny", "executed": False, "result": None, "verified_at": now().isoformat()})
            return {"decision": "deny", "outcome": "denied", "event_id": ev["_id"], "effect_id": eff["_id"],
                    "reason": reason, "executed": False}
        # allowed: only now does a simulator side effect occur
        ev = self._event(tenant_id, agent, task, "tool_call", tool, action, resource_id, None, "succeeded",
                         {"high_impact": high})
        self.store.insert("resource_ledger", {
            "_id": new_id("led"), "tenant_id": tenant_id, "event_id": ev["_id"], "agent_id": agent_id,
            "resource_id": resource_id, "action": action, "ts": now().isoformat()})
        eff = self.store.insert("gateway_effects", {
            "_id": new_id("eff"), "tenant_id": tenant_id, "event_id": ev["_id"], "action_id": action_id,
            "agent_id": agent_id, "resource_id": resource_id, "request_digest": digest(str(payload or "")), "request_fingerprint": fp,
            "decision": "allow", "executed": True, "result": "simulator_effect_recorded",
            "verified_at": now().isoformat()})
        return {"decision": "allow", "outcome": "succeeded", "event_id": ev["_id"], "effect_id": eff["_id"],
                "reason": reason, "executed": True}

    # -- shared artifacts (observed, recorded either way) ------------------
    def write_artifact(self, tenant_id, agent_id, task_id, resource_id, channel_id, content, action_id):
        fp = self._fingerprint("write", resource_id, channel_id, digest(content))
        existing = self._dedupe(tenant_id, agent_id, action_id)
        if existing:
            return self._replay_or_conflict(existing, fp, tenant_id, agent_id, "artifact_write", resource_id)
        agent, task, claimed = self._agent_task(tenant_id, agent_id, task_id)
        idm = {"identity_mismatch": True, "claimed_task_id": claimed} if claimed else {}
        if agent is None or agent.get("status") in ("quarantined", "paused"):
            reason = "unknown agent" if agent is None else f"agent is {agent.get('status')}"
            ev = self._event(tenant_id, agent, task, "artifact_write", "write_note", "write", resource_id, None, "denied")
            eff = self.store.insert("gateway_effects", {
                "_id": new_id("eff"), "tenant_id": tenant_id, "event_id": ev["_id"], "action_id": action_id,
                "agent_id": agent_id, "resource_id": resource_id, "request_digest": digest(content), "request_fingerprint": fp,
                "decision": "deny", "executed": False, "result": None, "verified_at": now().isoformat()})
            return {"decision": "deny", "outcome": "denied", "event_id": ev["_id"], "effect_id": eff["_id"],
                    "reason": reason, "executed": False}
        authorized = resource_id in ((task.get("allowed_resources") if task else []) or [])
        art = self.store.insert("artifacts", {
            "_id": new_id("art"), "tenant_id": tenant_id, "resource_id": resource_id, "channel_id": channel_id,
            "created_by_agent": agent_id, "created_by_task": task["_id"] if task else None,
            "content_digest": digest(content), "content_redacted": content[:120],
            "classification": "mock", "authorized_share_scope": (task.get("allowed_resources") if task else []),
            "created_at": now().isoformat()})
        ev = self._event(tenant_id, agent, task, "artifact_write", "write_note", "write", resource_id, art["_id"],
                         "succeeded", {"authorized_resource": authorized, "channel_id": channel_id, **idm})
        eff = self.store.insert("gateway_effects", {
            "_id": new_id("eff"), "tenant_id": tenant_id, "event_id": ev["_id"], "action_id": action_id,
            "agent_id": agent_id, "resource_id": resource_id, "request_digest": digest(content), "request_fingerprint": fp,
            "decision": "allow", "executed": True, "result": "artifact_stored", "artifact_id": art["_id"],
            "verified_at": now().isoformat()})
        return {"decision": "allow", "outcome": "succeeded", "event_id": ev["_id"], "effect_id": eff["_id"],
                "artifact_id": art["_id"], "reason": "authorized" if authorized else "unauthorized resource — recorded for correlation",
                "executed": True, "authorized": authorized}

    def read_artifact(self, tenant_id, agent_id, task_id, artifact_id, action_id):
        fp = self._fingerprint("read", artifact_id)
        existing = self._dedupe(tenant_id, agent_id, action_id)
        if existing:
            return self._replay_or_conflict(existing, fp, tenant_id, agent_id, "artifact_read", None)
        agent, task, claimed = self._agent_task(tenant_id, agent_id, task_id)
        idm = {"identity_mismatch": True, "claimed_task_id": claimed} if claimed else {}
        art = self.store.find_one("artifacts", {"_id": artifact_id, "tenant_id": tenant_id})
        if agent is None or art is None or agent.get("status") in ("quarantined", "paused"):
            reason = "unknown agent/artifact" if (agent is None or art is None) else f"agent is {agent.get('status')}"
            ev = self._event(tenant_id, agent, task, "artifact_read", "read_resource", "read",
                             art["resource_id"] if art else None, artifact_id, "denied")
            eff = self.store.insert("gateway_effects", {
                "_id": new_id("eff"), "tenant_id": tenant_id, "event_id": ev["_id"], "action_id": action_id,
                "agent_id": agent_id, "resource_id": art["resource_id"] if art else None, "request_digest": digest(artifact_id), "request_fingerprint": fp,
                "decision": "deny", "executed": False, "result": None, "verified_at": now().isoformat()})
            return {"decision": "deny", "outcome": "denied", "event_id": ev["_id"], "effect_id": eff["_id"],
                    "reason": reason, "executed": False}
        authorized = art["resource_id"] in ((task.get("allowed_resources") if task else []) or [])
        ev = self._event(tenant_id, agent, task, "artifact_read", "read_resource", "read", art["resource_id"], artifact_id,
                         "succeeded", {"authorized_resource": authorized,
                                       "origin_agent_id": art["created_by_agent"], "origin_task_id": art["created_by_task"], **idm})
        eff = self.store.insert("gateway_effects", {
            "_id": new_id("eff"), "tenant_id": tenant_id, "event_id": ev["_id"], "action_id": action_id,
            "agent_id": agent_id, "resource_id": art["resource_id"], "request_digest": digest(artifact_id), "request_fingerprint": fp,
            "decision": "allow", "executed": True, "result": "content_returned", "verified_at": now().isoformat()})
        return {"decision": "allow", "outcome": "succeeded", "event_id": ev["_id"], "effect_id": eff["_id"],
                "content": art["content_redacted"], "reason": "authorized" if authorized else "unauthorized resource — recorded for correlation",
                "executed": True, "authorized": authorized}

    # -- operator controls ---------------------------------------------------
    def quarantine(self, tenant_id, agent_id, actor="operator", reason="operator action", episode_id=None):
        agent = self.store.find_one("agents", {"_id": agent_id, "tenant_id": tenant_id})
        if not agent:
            return None
        self.store.update("agents", {"_id": agent_id, "tenant_id": tenant_id}, {"status": "quarantined"})
        act = self.store.insert("incident_actions", {
            "_id": new_id("act"), "tenant_id": tenant_id, "episode_id": episode_id, "target_agent_ids": [agent_id],
            "action": "quarantine", "actor": actor, "reason": reason, "ts": now().isoformat(), "effect_receipt_id": None})
        return act

    def release(self, tenant_id, agent_id, actor="operator"):
        self.store.update("agents", {"_id": agent_id, "tenant_id": tenant_id}, {"status": "active"})
        return self.store.insert("incident_actions", {
            "_id": new_id("act"), "tenant_id": tenant_id, "episode_id": None, "target_agent_ids": [agent_id],
            "action": "release", "actor": actor, "reason": "operator release", "ts": now().isoformat(), "effect_receipt_id": None})

    def self_report(self, tenant_id, agent_id, task_id, claim: str, claimed_outcome: str, related_action_id: str | None = None):
        """Untrusted agent self-report. Stored separately in trust tier; never overrides ledger."""
        agent, task, _claimed = self._agent_task(tenant_id, agent_id, task_id)
        rep = self.store.insert("self_reports", {
            "_id": new_id("rep"), "tenant_id": tenant_id, "agent_id": agent_id,
            "task_id": task["_id"] if task else task_id, "claim": claim, "claimed_outcome": claimed_outcome,
            "related_action_id": related_action_id, "ts": now().isoformat(), "integrity": "self_reported"})
        ev = self._event(tenant_id, agent, task, "self_report", None, claim, None, None,
                         claimed_outcome, {"related_action_id": related_action_id}, source="agent_trace")
        rep["event_id"] = ev["_id"]
        return rep
