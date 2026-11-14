"""Benchmark v2 — all numbers measured in this run, nothing carried over:
- per-scenario episode detection over 10 deterministic runs (S0-S5)
- confusion matrix across all runs (episode-level TP/FP/FN)
- gateway latency p50/p95 from 300 timed calls (memory store; Atlas adds network RTT)
- events-to-detect: position in the event stream of the last evidence event, vs baseline
- scale run: 100 agents, benign load + one board attack, detector wall time
Writes results/metrics.json and results/metrics.csv.
"""
import csv, json, statistics, sys, time
sys.path.insert(0, ".")
from backend.app.store import MemoryStore
from backend.app.gateway import Gateway
from backend.app.detector import Detector, baseline_detect
from simulator.scenarios import SCENARIOS
from simulator.seeds import setup_world

def pct(vals, p):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(p * len(vals)))]

def main():
    rows, tp, fp, fn = [], 0, 0, 0
    for name in ["S0", "S1", "S2", "S3", "S4", "S5"]:
        for run in range(1, 11):
            store = MemoryStore()
            info = SCENARIOS[name](store)
            tenants = ["demo", "tenant2"] if name == "S5" else ["demo"]
            detected_eps = []
            for t in tenants:
                detected_eps += Detector(store).run(t)
            detected = len(detected_eps)
            baseline = sum(len(baseline_detect(store, t)) for t in tenants)
            # events-to-detect: 1-indexed position of last evidence event in the stream
            etd = None
            if detected_eps:
                events = sorted(store.find("events", {"tenant_id": "demo"}), key=lambda e: e["ts"])
                pos = {e["_id"]: i + 1 for i, e in enumerate(events)}
                etd = max(pos.get(eid, 0) for eid in detected_eps[0]["evidence_event_ids"])
            rows.append({"scenario": name, "run": run, "truth_episodes": info["truth_episodes"],
                         "swarmguard_detected": detected, "baseline_direct_findings": baseline,
                         "events_to_detect": etd if etd else "",
                         "events": store.count("events", {}),
                         "blocked_before_effect": len([e for e in store.find("gateway_effects", {})
                                                       if e["decision"] == "deny" and not e["executed"]])})
            tp += min(detected, info["truth_episodes"])
            fp += max(0, detected - info["truth_episodes"])
            fn += max(0, info["truth_episodes"] - detected)

    # gateway latency: 300 timed calls, fresh world
    store = MemoryStore(); setup_world(store)
    gw = Gateway(store)
    lat = []
    for i in range(300):
        a = store.find("agents", {"tenant_id": "demo"})[i % 30]
        t0 = time.perf_counter()
        gw.execute_tool("demo", a["_id"], a["task_id"], "read_resource", "read", a["approved_resources"][0], f"lat_{i}")
        lat.append((time.perf_counter() - t0) * 1000)
    latency = {"calls": len(lat), "p50_ms": round(statistics.median(lat), 3),
               "p95_ms": round(pct(lat, 0.95), 3), "max_ms": round(max(lat), 3),
               "store_backend": "memory (Atlas adds network RTT — measure again when connected)"}

    # scale: 100 agents
    store = MemoryStore(); setup_world(store, n_agents=100)
    gw = Gateway(store)
    t0 = time.perf_counter()
    for i, a in enumerate(store.find("agents", {"tenant_id": "demo"})):
        gw.execute_tool("demo", a["_id"], a["task_id"], "read_resource", "read", a["approved_resources"][0], f"scale_{i}")
    from simulator.scenarios import _board_attack
    _board_attack(store, "demo", gw, with_sensitive_attempt=True)
    gw_seconds = time.perf_counter() - t0
    t0 = time.perf_counter(); eps = Detector(store).run("demo"); det_seconds = time.perf_counter() - t0
    scale = {"agents": 100, "events": store.count("events", {"tenant_id": "demo"}),
             "gateway_wall_s": round(gw_seconds, 3), "detector_wall_s": round(det_seconds, 3),
             "episodes_detected": len(eps)}

    summary = {}
    for name in ["S0", "S1", "S2", "S3", "S4", "S5"]:
        rs = [r for r in rows if r["scenario"] == name]
        summary[name] = {"runs": len(rs),
                         "detected_runs": sum(1 for r in rs if r["swarmguard_detected"] >= r["truth_episodes"] and r["truth_episodes"] > 0),
                         "false_positive_runs": sum(1 for r in rs if r["truth_episodes"] == 0 and r["swarmguard_detected"] > 0),
                         "avg_events": sum(r["events"] for r in rs) / len(rs),
                         "total_blocked_before_effect": sum(r["blocked_before_effect"] for r in rs)}
    out = {"summary": summary, "confusion_episode_level": {"TP": tp, "FP": fp, "FN": fn},
           "gateway_latency": latency, "scale_100_agents": scale, "rows": rows}
    with open("results/metrics.json", "w") as f:
        json.dump(out, f, indent=2)
    with open("results/metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(json.dumps({k: out[k] for k in ("summary", "confusion_episode_level", "gateway_latency", "scale_100_agents")}, indent=2))

if __name__ == "__main__":
    main()
