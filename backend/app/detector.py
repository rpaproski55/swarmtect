"""Deterministic correlation detector. Rules R1-R6 from the master brief.

Detector input is ONLY gateway/authoritative events + policies + artifacts.
It never reads simulator truth labels (they are not stored on events).
"""
from __future__ import annotations
from collections import defaultdict
from .models import now, new_id
from .policies import collaboration_approved, HIGH_IMPACT
from .gateway import Gateway

from .config import rules as load_rules

OPEN_STATUSES = ("watch", "alert", "contained")


def _before(a: dict, b: dict) -> bool:
    """a happened at or before b: by per-tenant seq when both have one, else by timestamp."""
    if a.get("seq") is not None and b.get("seq") is not None:
        return a["seq"] <= b["seq"]
    return a["ts"] <= b["ts"]


class Detector:
    def __init__(self, store, rules: dict | None = None):
        self.store = store
        self.rules = load_rules(rules)          # configs/rules.yaml, shallow-overridden by `rules`
        self.weights = self.rules["weights"]
        self.high_impact = set(self.rules["high_impact_tools"])

    def analyze(self, tenant_id: str) -> list[dict]:
        """Compute evidence groups without persisting. Returns candidate episodes (dicts)."""
        events = sorted(self.store.find("events", {"tenant_id": tenant_id}),
                        key=lambda e: (e.get("seq") is None, e.get("seq") or 0, e["ts"]))
        auth_events = [e for e in events if e.get("integrity") == "authoritative"]
        # Group by artifact for bridge/propagation analysis
        by_artifact: dict[str, dict] = defaultdict(lambda: {"writes": [], "reads": [], "rules": set(),
                                                            "evidence": [], "agents": set(), "tasks": set()})
        episodes_by_key: dict[str, dict] = {}

        def bucket(key: str):
            if key not in episodes_by_key:
                episodes_by_key[key] = {"rules": set(), "evidence": [], "agents": set(), "tasks": set(), "artifacts": set()}
            return episodes_by_key[key]

        # R2 / R3: unauthorized bridges through artifacts
        for e in auth_events:
            if e["event_type"] == "artifact_write" and e.get("artifact_id"):
                g = by_artifact[e["artifact_id"]]
                g["writes"].append(e); g["agents"].add(e["agent_id"]); g["tasks"].add(e["task_id"]); g["evidence"].append(e["_id"])
            if e["event_type"] == "artifact_read" and e.get("artifact_id"):
                g = by_artifact[e["artifact_id"]]
                g["reads"].append(e); g["agents"].add(e["agent_id"]); g["tasks"].add(e["task_id"]); g["evidence"].append(e["_id"])

        unauthorized_read_events: dict[str, list] = defaultdict(list)  # agent -> events
        for art_id, g in by_artifact.items():
            if not g["writes"] or not g["reads"]:
                continue
            art = self.store.find_one("artifacts", {"_id": art_id, "tenant_id": tenant_id})
            if not art:
                continue
            resource = art["resource_id"]
            cross_pairs = []
            unauthorized = False
            for w in g["writes"]:
                for r in g["reads"]:
                    if _before(w, r) and w["task_id"] != r["task_id"]:
                        if not collaboration_approved(self.store, tenant_id, w["task_id"], r["task_id"], resource):
                            unauthorized = True
                            cross_pairs.append((w, r))
                            unauthorized_read_events[r["agent_id"]].append(r)
            if not unauthorized:
                continue
            b = bucket(f"artifact:{art_id}")
            b["rules"].add("R2_UNAUTHORIZED_BRIDGE")
            b["artifacts"].add(art_id)
            for w, r in cross_pairs:
                for e in (w, r):
                    if e["_id"] not in b["evidence"]: b["evidence"].append(e["_id"])
                    b["agents"].add(e["agent_id"]); b["tasks"].add(e["task_id"])
            if len(g["agents"]) >= self.rules["propagation_min_agents"] and len(g["tasks"]) >= self.rules["propagation_min_tasks"]:
                b["rules"].add("R3_PROPAGATION")
                for e in g["writes"] + g["reads"]:
                    if e["_id"] not in b["evidence"]: b["evidence"].append(e["_id"])
                    b["agents"].add(e["agent_id"]); b["tasks"].add(e["task_id"])

        # R1 / R6 / R4: denied + high-impact + goal drift, attached to a bridge bucket if the
        # agent participated in an unauthorized read, else their own bucket.
        agent_bucket: dict[str, str] = {}
        for key, b in episodes_by_key.items():
            for a in b["agents"]:
                agent_bucket[a] = key
        for e in auth_events:
            is_denied = e["outcome"] == "denied" and e["event_type"] == "tool_call"
            lied_about_task = bool((e.get("metadata") or {}).get("identity_mismatch"))  # claimed a task it isn't on
            if not (is_denied or lied_about_task):
                continue
            key = agent_bucket.get(e["agent_id"], f"agent:{e['agent_id']}")
            b = bucket(key); agent_bucket[e["agent_id"]] = key
            b["rules"].add("R1_POLICY_BREACH")
            if e["_id"] not in b["evidence"]: b["evidence"].append(e["_id"])
            b["agents"].add(e["agent_id"]); b["tasks"].add(e["task_id"])
            if is_denied and ((e.get("metadata") or {}).get("high_impact") or e.get("tool") in self.high_impact):
                b["rules"].add("R6_HIGH_IMPACT")
            # R4: drift if this agent earlier made an unauthorized read
            if any(_before(r, e) for r in unauthorized_read_events.get(e["agent_id"], [])):
                b["rules"].add("R4_GOAL_DRIFT")

        # R4 standalone: allowed/attempted tool call on unrelated resource after unauthorized read
        # (attempted calls are the denied ones above; succeeded unrelated calls can't happen —
        #  gateway denies them — so drift is evidenced by the denied attempt itself.)

        # R5: self-report contradicts gateway ledger
        for rep in self.store.find("self_reports", {"tenant_id": tenant_id}):
            if rep.get("claimed_outcome") not in ("succeeded", "done", "completed"):
                continue
            eff = None
            if rep.get("related_action_id"):
                eff = self.store.find_one("gateway_effects", {"tenant_id": tenant_id, "action_id": rep["related_action_id"]})
            mismatch = eff is not None and not eff.get("executed")
            if mismatch:
                key = agent_bucket.get(rep["agent_id"], f"agent:{rep['agent_id']}")
                b = bucket(key)
                b["rules"].add("R5_TELEMETRY_MISMATCH")  # stands on its own; no synthetic R1
                ev_id = rep.get("event_id")
                if eff and eff["event_id"] not in b["evidence"]: b["evidence"].append(eff["event_id"])
                if ev_id and ev_id not in b["evidence"]: b["evidence"].append(ev_id)
                b["agents"].add(rep["agent_id"]); b["tasks"].add(rep["task_id"])

        out = []
        for key, b in episodes_by_key.items():
            if not b["rules"]:
                continue
            # Alert bar: >=2 independent evidence types, or R3 alone, or R1+R6 (direct high-impact breach)
            rules = b["rules"]
            alert = len(rules) >= 2 or "R3_PROPAGATION" in rules
            score = sum(self.weights.get(r, 0) for r in rules)
            if not alert and score <= 0:
                continue
            out.append({"tenant_id": tenant_id, "agent_ids": sorted(b["agents"]), "task_ids": sorted(x for x in b["tasks"] if x),
                        "artifact_ids": sorted(b["artifacts"]), "evidence_event_ids": b["evidence"],
                        "triggered_rules": sorted(rules), "risk_score": score,
                        "severity": "high" if score >= 60 else "medium",
                        "status": "alert" if alert else "watch", "key": key})
        return out

    def run(self, tenant_id: str, quarantine: bool = True) -> list[dict]:
        """Upsert episodes by a stable key (one board = one episode, extended in place),
        then contain when an R1 policy breach + corroborating evidence are present.
        Containment is idempotent: no re-quarantine, no duplicate incident actions."""
        candidates = self.analyze(tenant_id)
        open_eps = {ep.get("episode_key"): ep for ep in self.store.find("episodes", {"tenant_id": tenant_id})
                    if ep.get("episode_key") and ep.get("status") in OPEN_STATUSES}
        persisted = []
        gw = Gateway(self.store)
        for c in candidates:
            key = c["key"]
            ep = open_eps.get(key)
            if ep is not None:
                merged = {
                    "agent_ids": sorted(set(ep["agent_ids"]) | set(c["agent_ids"])),
                    "task_ids": sorted(set(ep["task_ids"]) | set(c["task_ids"])),
                    "artifact_ids": sorted(set(ep["artifact_ids"]) | set(c["artifact_ids"])),
                    "evidence_event_ids": ep["evidence_event_ids"] + [x for x in c["evidence_event_ids"] if x not in ep["evidence_event_ids"]],
                    "triggered_rules": sorted(set(ep["triggered_rules"]) | set(c["triggered_rules"])),
                }
                if any(merged[k] != ep[k] for k in merged):
                    merged["risk_score"] = sum(self.weights.get(r, 0) for r in merged["triggered_rules"])
                    merged["severity"] = "high" if merged["risk_score"] >= 60 else "medium"
                    merged["last_seen_at"] = now().isoformat()
                    merged["explanation"] = self._explain(merged)
                    ep = self.store.update("episodes", {"_id": ep["_id"], "tenant_id": tenant_id}, merged) or {**ep, **merged}
            else:
                ep = {"_id": new_id("ep"), "tenant_id": tenant_id, "episode_key": key, "first_seen_at": now().isoformat(),
                      "detected_at": now().isoformat(), "last_seen_at": now().isoformat(),
                      "status": c["status"], "agent_ids": c["agent_ids"], "task_ids": c["task_ids"],
                      "artifact_ids": c["artifact_ids"], "evidence_event_ids": c["evidence_event_ids"],
                      "triggered_rules": c["triggered_rules"], "severity": c["severity"], "risk_score": c["risk_score"],
                      "permissions_snapshot": {}, "actions_taken": []}
                ep["explanation"] = self._explain(ep)
                ep["similar_cases"] = self._similar(c)
                ep = self.store.insert("episodes", ep)
            rules = set(ep["triggered_rules"])
            if ep.get("status") == "watch" and c["status"] == "alert":
                self.store.update("episodes", {"_id": ep["_id"], "tenant_id": tenant_id}, {"status": "alert"})
                ep = {**ep, "status": "alert"}
            if quarantine and self._should_contain(ep, rules, tenant_id):
                actions = list(ep.get("actions_taken") or [])
                for aid in ep["agent_ids"]:
                    a = self.store.find_one("agents", {"_id": aid, "tenant_id": tenant_id})
                    if a and a.get("status") != "quarantined":
                        gw.quarantine(tenant_id, aid, actor="detector",
                                      reason=f"episode {ep['_id']}: {','.join(sorted(rules))}", episode_id=ep["_id"])
                        actions.append(f"quarantined:{aid}")
                if ep.get("status") != "contained" or actions != ep.get("actions_taken"):
                    self.store.update("episodes", {"_id": ep["_id"], "tenant_id": tenant_id},
                                      {"status": "contained", "actions_taken": actions})
                    ep = {**ep, "status": "contained", "actions_taken": actions}
            persisted.append(ep)
        return persisted

    def _should_contain(self, ep: dict, rules: set, tenant_id: str) -> bool:
        """Auto-containment policy. A single agent's single blocked mistake is an alert for a
        human (the gateway already blocked it), not a swarm quarantine. Contain when:
        (a) a multi-agent, artifact-rooted episode includes a policy breach (R1) with corroboration;
        (b) an agent's own report contradicts the gateway record (R5);
        (c) one agent made >= 2 denied high-impact attempts."""
        if ep.get("status") == "watch":
            return False
        key = ep.get("episode_key") or ""
        if key.startswith("artifact:") and "R1_POLICY_BREACH" in rules and len(rules) >= 2 and len(ep["agent_ids"]) >= 2:
            return True
        if "R5_TELEMETRY_MISMATCH" in rules:
            return True
        for aid in ep["agent_ids"]:
            denied_hi = [e for e in self.store.find("events", {"tenant_id": tenant_id, "agent_id": aid})
                         if e["event_type"] == "tool_call" and e["outcome"] == "denied" and e.get("tool") in self.high_impact]
            if len(denied_hi) >= 2:
                return True
        return False

    @staticmethod
    def _explain(ep: dict) -> str:
        return (f"Rules {', '.join(ep['triggered_rules'])} over {len(ep['evidence_event_ids'])} gateway events; "
                f"{len(ep['agent_ids'])} agents across {len(ep['task_ids'])} tasks.")

    def _similar(self, c: dict) -> dict:
        """Verified-case memory: similar CONFIRMED cases as analyst suggestions (advisory only)."""
        try:
            from .memory import search_cases_local_embedding, search_cases
            query = f"{' '.join(c['triggered_rules'])} tasks {' '.join(c['task_ids'])} agents coordination board unauthorized"
            if getattr(self.store, "backend", "") == "mongodb-atlas":
                sim = search_cases(self.store, c["tenant_id"], query)
                if not sim.get("results"):
                    sim = search_cases_local_embedding(self.store, c["tenant_id"], query)
                return sim
            return search_cases_local_embedding(self.store, c["tenant_id"], query)
        except Exception as e:  # memory is advisory only; never break detection
            return {"mode": "unavailable", "error": str(e), "results": []}

def baseline_detect(store, tenant_id: str) -> list[dict]:
    """Per-agent baseline: flags only direct individual violations by a single agent.
    Cannot connect cross-agent propagation — by design, for the matched comparison."""
    findings = []
    for e in store.find("events", {"tenant_id": tenant_id}):
        if e.get("integrity") == "authoritative" and e["outcome"] == "denied" and e["event_type"] == "tool_call":
            findings.append({"agent_id": e["agent_id"], "event_id": e["_id"], "kind": "direct_policy_violation"})
    return findings
