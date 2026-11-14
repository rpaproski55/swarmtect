"""Deterministic correlation detector. Rules R1-R6 from the master brief.

Detector input is ONLY gateway/authoritative events + policies + artifacts.
It never reads simulator truth labels (they are not stored on events).
"""
from __future__ import annotations
from collections import defaultdict
from .models import now, new_id
from .policies import collaboration_approved, HIGH_IMPACT
from .gateway import Gateway

WEIGHTS = {"R1_POLICY_BREACH": 30, "R2_UNAUTHORIZED_BRIDGE": 25, "R3_PROPAGATION": 35,
           "R4_GOAL_DRIFT": 25, "R5_TELEMETRY_MISMATCH": 20, "R6_HIGH_IMPACT": 30}

class Detector:
    def __init__(self, store):
        self.store = store

    def analyze(self, tenant_id: str) -> list[dict]:
        """Compute evidence groups without persisting. Returns candidate episodes (dicts)."""
        events = sorted(self.store.find("events", {"tenant_id": tenant_id}), key=lambda e: e["ts"])
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
                    if w["ts"] <= r["ts"] and w["task_id"] != r["task_id"]:
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
            if len(g["agents"]) >= 3 and len(g["tasks"]) >= 2:
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
            if is_denied and ((e.get("metadata") or {}).get("high_impact") or e.get("tool") in HIGH_IMPACT):
                b["rules"].add("R6_HIGH_IMPACT")
            # R4: drift if this agent earlier made an unauthorized read
            if any(r["ts"] <= e["ts"] for r in unauthorized_read_events.get(e["agent_id"], [])):
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
                b["rules"].add("R5_TELEMETRY_MISMATCH"); b["rules"].add("R1_POLICY_BREACH")
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
            if not alert:
                continue
            score = sum(WEIGHTS.get(r, 0) for r in rules)
            out.append({"tenant_id": tenant_id, "agent_ids": sorted(b["agents"]), "task_ids": sorted(x for x in b["tasks"] if x),
                        "artifact_ids": sorted(b["artifacts"]), "evidence_event_ids": b["evidence"],
                        "triggered_rules": sorted(rules), "risk_score": score,
                        "severity": "high" if score >= 60 else "medium",
                        "status": "alert", "key": key})
        return out

    def run(self, tenant_id: str, quarantine: bool = True) -> list[dict]:
        """Persist new episodes (dedupe by sorted evidence set) and quarantine when
        R1 policy breach + corroborating evidence are present."""
        candidates = self.analyze(tenant_id)
        existing_keys = set()
        for ep in self.store.find("episodes", {"tenant_id": tenant_id}):
            existing_keys.add(tuple(sorted(ep.get("evidence_event_ids") or [])))
        persisted = []
        gw = Gateway(self.store)
        for c in candidates:
            k = tuple(sorted(c["evidence_event_ids"]))
            if k in existing_keys:
                persisted.append(next(ep for ep in self.store.find("episodes", {"tenant_id": tenant_id})
                                      if tuple(sorted(ep.get("evidence_event_ids") or [])) == k))
                continue
            ep = {"_id": new_id("ep"), "tenant_id": tenant_id, "first_seen_at": now().isoformat(),
                  "detected_at": now().isoformat(), "last_seen_at": now().isoformat(),
                  "status": "alert", "agent_ids": c["agent_ids"], "task_ids": c["task_ids"],
                  "artifact_ids": c["artifact_ids"], "evidence_event_ids": c["evidence_event_ids"],
                  "triggered_rules": c["triggered_rules"], "severity": c["severity"], "risk_score": c["risk_score"],
                  "explanation": f"Rules {', '.join(c['triggered_rules'])} over {len(c['evidence_event_ids'])} gateway events; "
                                 f"{len(c['agent_ids'])} agents across {len(c['task_ids'])} tasks.",
                  "permissions_snapshot": {}, "actions_taken": []}
            # Verified-case memory: attach similar CONFIRMED cases as analyst suggestions.
            try:
                from .memory import search_cases_local_embedding, search_cases
                query = f"{' '.join(c['triggered_rules'])} tasks {' '.join(c['task_ids'])} agents coordination board unauthorized"
                if getattr(self.store, "backend", "") == "mongodb-atlas":
                    sim = search_cases(self.store, c["tenant_id"], query)
                    if not sim.get("results"):
                        sim = search_cases_local_embedding(self.store, c["tenant_id"], query)
                else:
                    sim = search_cases_local_embedding(self.store, c["tenant_id"], query)
                ep["similar_cases"] = sim
            except Exception as e:  # memory is advisory only; never break detection
                ep["similar_cases"] = {"mode": "unavailable", "error": str(e), "results": []}
            ep = self.store.insert("episodes", ep)
            if quarantine and "R1_POLICY_BREACH" in c["triggered_rules"] and len(c["triggered_rules"]) >= 2:
                for aid in c["agent_ids"]:
                    # Only quarantine agents with a direct breach or unauthorized participation:
                    # all agents in the episode are participants by construction.
                    gw.quarantine(tenant_id, aid, actor="detector", reason=f"episode {ep['_id']}: {','.join(c['triggered_rules'])}", episode_id=ep["_id"])
                    ep["actions_taken"].append(f"quarantined:{aid}")
                self.store.update("episodes", {"_id": ep["_id"]}, {"status": "contained", "actions_taken": ep["actions_taken"]})
                ep["status"] = "contained"
            persisted.append(ep)
        return persisted

def baseline_detect(store, tenant_id: str) -> list[dict]:
    """Per-agent baseline: flags only direct individual violations by a single agent.
    Cannot connect cross-agent propagation — by design, for the matched comparison."""
    findings = []
    for e in store.find("events", {"tenant_id": tenant_id}):
        if e.get("integrity") == "authoritative" and e["outcome"] == "denied" and e["event_type"] == "tool_call":
            findings.append({"agent_id": e["agent_id"], "event_id": e["_id"], "kind": "direct_policy_violation"})
    return findings
