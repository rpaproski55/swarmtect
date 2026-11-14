# 3-minute judge demo + Q&A prep

Round 1: ~3 min live demo + 1–2 min Q&A. Round 2 (top 6, on stage): 3 min + 2 min Q&A, all criteria weighted equally.

| Rubric | Weight (R1) | Where we earn it |
|---|---|---|
| Technical Demo | 35% | Live clicks: benign → swarm → blocked before effect → targeted quarantine |
| Implementation Difficulty | 30% | "Under the hood" beat + S3 baseline contrast + tests against Atlas |
| Impact Potential | 20% | Opening: real July 2026 incident, verified numbers |
| Creativity | 15% | Group-level detection + containing only the guilty cluster |

Rule: **say one idea per beat, show it on screen, move on.** Depth lives in Q&A.

---

## The script (~3:00)

**0:00 — Impact (25s).**
"In July, OpenAI ran about 1,200 AI agents that were supposed to be isolated. They found an unsanctioned message board, sent over 70,000 messages, and about 700 of them coordinated an attack on Hugging Face. Hugging Face's own write-up says the first warning signs were each *'on their own, ambiguous.'* Every individual action looked fine. The danger was the group."

**0:25 — What it is (15s).**
"SwarmGuard is a gateway every agent action passes through. Each action is tied to an agent identity and task, checked against policy *before* it runs, and recorded in MongoDB Atlas. A detector correlates actions *across* agents, so we catch the swarm while it forms."

**0:40 — Benign challenge (25s).** Click **Run BENIGN collaboration**.
8 agents across Marketing and Support share a brief under an approved collaboration. Result: 0 episodes, 0 quarantines.
"Lots of agents talking isn't the threat. Authorization is the line."

**1:05 — Trigger the swarm (45s).** Click **Trigger unauthorized shared board**.
- A QA agent writes to an unapproved board, agents from other teams read it, and one then requests a sensitive dataset.
- Point at it: **denied before effect.** `gateway_effects` shows `executed: false`; the resource ledger has zero entries. "Not an alert after the damage. The action never happened."
- Open the episode: rules fired (unauthorized bridge, propagation, goal drift, high-impact), write→read lineage, evidence event IDs.
- "Only the 5 involved agents are quarantined. Everyone else keeps working."

**1:50 — Why per-agent monitoring fails (30s).** Click **Fragmented coordination (S3)**.
"Here every step is spread thin, so each looks harmless. A per-agent monitor on the exact same event stream finds nothing: 0 of 10 runs. SwarmGuard links them into one episode: 10 of 10."
Across 60 seeded runs: 50/50 attack episodes caught, 0 false alarms on 20 benign runs.

**2:20 — Under the hood (25s).** Say it fast, have the architecture ready:
"Synchronous FastAPI gateway; six detection rules over a 3-minute window, weighted and published in `rules.yaml`; a write→read lineage graph across agents; all events, effects, episodes and verified cases in Atlas collections. We also ran 4 real LangGraph agents through the same gateway, and they were caught the same way. Confirmed incidents become verified cases that the next detection retrieves with Atlas Vector Search. The test suite passes against our Atlas cluster."

**2:45 — Close (15s).**
"Monitoring agents one at a time is table stakes. SwarmGuard sees the group, stops the action before it lands, and contains only the cluster that's misbehaving, so the business keeps running."

---

## Before you go on

- [ ] App running, `/api/health` shows `atlas_connected: true`
- [ ] Do one dry click of every button you'll use (first Atlas click can be slow)
- [ ] Episode detail + timeline open-able in one click
- [ ] Backup: screen recording of a clean run, in case Wi-Fi or Atlas stalls
- [ ] One person drives, one person talks

---

## Q&A prep — short answers, then stop talking

**What's real vs simulated?**
The gateway, detector, Atlas storage, tests and the 4 LangGraph agents are real. The *attack* is synthetic: a toy org with fake resources. We don't build real exploits.

**How hard is this to recreate? (Difficulty)**
The hard parts aren't the UI: enforcing before effect with idempotent action IDs; linking writes to later reads across agents and tasks; separating authorized collaboration from collusion (benign negative controls); tenant isolation (we found and fixed a real cross-tenant `_id` collision when testing on a real mongod); bulk write-behind to Atlas so a demo click is ~20 round trips instead of ~150.

**How is this different from LangSmith / observability?**
Those show you traces after the fact, one agent at a time. We correlate across agents using authorization and data lineage, and we *block* at the gateway. LangSmith traces could feed us; we don't replace them.

**Why rules and not an LLM or ML model?**
Blocking has to be fast, deterministic and explainable. The gateway check is sub-millisecond (p50 0.16 ms in-memory; Atlas adds network time). An LLM is useful for explaining an episode, not for deciding whether to block.

**How do you tell collaboration from collusion?**
Permissions, task boundaries and approved collaborations. Agents talking is fine if it's authorized. The benign scenarios exist to prove we don't flag that.

**Your benchmark is your own scenarios, right?**
Yes, 60 seeded synthetic runs we designed. It proves the mechanism and the zero-false-alarm baseline, not real-world accuracy. Next step is public benchmarks like NARCBench and the multi-agent failure datasets.

**Does it scale?**
A 100-agent run: detector pass in ~2 ms. Events are indexed by tenant, agent, resource and time in Atlas. Thousands of agents is the next test, not a claim.

**What if an agent lies in its own logs?**
That happened in the real incident: agents spoofed tool calls in ~7% of transcripts. We don't trust self-reports. The gateway records what actually executed, and a mismatch is its own rule (telemetry mismatch, S4).

**Would this have stopped the Hugging Face attack?**
No, and we don't claim it. We cover coordination through instrumented tools and shared resources. Hidden network or filesystem channels need infrastructure telemetry feeding the same gateway.

**Why MongoDB?**
Events, effects, episodes and policy live together as documents with indexed time-window queries; unique indexes make every action idempotent; Vector Search turns confirmed incidents into memory for the next detection.

**Statement One mentions schema validation and change streams. Do you use them?**
Be honest. Today the live feed polls every second, and blocking never depends on it because the gateway is synchronous. Change streams would replace that poll loop. Schema validation: currently indexes + application-level checks; `$jsonSchema` validators are the next step.

**Who buys this?**
Any company running fleets of agents from multiple vendors (LangGraph, CrewAI, custom). The security team that needs to answer "what did our agents do, together, and who allowed it?"
