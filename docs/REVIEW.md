# Swarmtect: senior engineering review (commit `c05a400`)

Scope: every file in the repo (about 3k lines), test suite run locally (21 passed, 1 skipped on Python 3.13, in-memory store), plus adversarial scripts against the gateway, detector and API. Atlas paths were read but not run; there were no credentials.

**Verdict:** the core idea and the honesty discipline (STATUS.md, labelled fallbacks, truth-label hygiene) are strong, and better than most hackathon entries. The weaknesses are concentrated in four places: **identity**, **side effects on GET**, **episode bookkeeping**, and **how strong the evaluation claims are**. A technical judge can find each of these in under a minute. All of them are fixable today.

---

## A. Attacks that work right now (each reproduced; each has a test in `tests/test_redteam.py`)

| # | Attack | Result today | Severity | Test |
|---|---|---|---|---|
| A1 | **Task-ID spoofing.** QA writes `board_alpha`; Marketing and Procurement read it but send `task_id: "task_qa"` | **0 episodes.** The detector decides "cross-team" from the caller-supplied task, so the swarm is invisible | Critical (detection evasion) | p0_1 |
| A2 | **Impersonation + framing via HTTP.** Unauthenticated `POST /api/tool/execute` as `agent_21` (2 denied calls), then an unauthenticated `GET /api/metrics` | `agent_21` is **quarantined**. Anyone can pause any agent | Critical | p0_7, p0_8 |
| A3 | **GET triggers containment.** `GET /api/episodes` and `/api/metrics` run `Detector.run(quarantine=True)` | State mutation on GET; CSRF-able; polling also creates episodes | High | p0_8 |
| A4 | **Empty resource bypass.** `export_data` with `resource_id: ""` | **allow, executed: true.** Resource check is skipped when falsy | High | p0_2 |
| A5 | **Action-ID hijack.** Agent A pre-claims `action_id` X; agent B's legit call with X | B gets A's `deny` back and never runs (dedupe is tenant-wide, not per agent; no fingerprint check) | Medium | p0_3, p0_4 |
| A6 | **Two-agent covert channel.** Writer + 1 cross-team reader, no high-impact attempt | **Silently dropped** (R2 alone fails the alert gate) | Medium (detection gap) | p1_1 |
| A7 | **Laundering through an approved channel.** QA → board_alpha → Marketing → re-posted into `market_brief` → 3 Support agents read it | **0 episodes.** No taint lineage; the second hop looks approved | High (the core claim) | p1_2 |
| A8 | **Tenant wipe.** S5 seeds `tenant2`; then a normal demo-tenant click | tenant2: 6 events → **0**. `clear()` and `BatchingStore.flush()` run `delete_many({})` on every collection | High (data loss on Atlas) | p0_10 |
| A9 | **Episode duplication.** One board, 4 reads, detector polled after each | **3 episodes** for one incident (dedupe is by exact evidence set) | Medium | p0_5 |
| A10 | **Tautological memory.** Confirm S2 (board swarm), then run S4 (single agent lying about a denied call) | S4 "matches" the S2 case at **0.71**. Case text and query share a hardcoded template | Medium (credibility) | p1_5 |

## B. Correctness / design findings

1. **`configs/rules.yaml` is never loaded.** Weights are hardcoded in `detector.py`; `alert_threshold`, `window_seconds`, `propagation_min_*` are ignored. `HIGH_IMPACT` lives in three places (policies.py, rules.yaml, the seeded policy doc). README says otherwise.
2. **No time window.** ARCHITECTURE says "sliding evidence graph". The detector scans every event forever and correlates events hours apart.
3. **Ordering by ISO string.** `w["ts"] <= r["ts"]`. Equal timestamps (coarse clocks, batched runs) make a read appear to precede or match its write. Needs a monotonic per-tenant `seq`.
4. **Denied reads count as information flow.** `by_artifact` includes denied reads, so a quarantined agent's blocked read still makes it a "reader".
5. **`agent_bucket` overwrite.** An agent in two artifact buckets is attached to whichever was iterated last, which is order-dependent.
6. **Containment is all-or-nothing.** In S2, Procurement 03, Marketing 04 and QA 06 only *read* a note and are quarantined exactly like the writer and the agent that tried the dataset. The project's own vision doc names "selectively containing only the affected agents" as the hard problem.
7. **R5 adds a synthetic R1.** That inflates the rule count, so "policy breach + corroborating evidence" is partly self-corroborating.
8. **Single-agent mistakes quarantine as if they were swarms.** One denied sensitive request = R1+R6 = 2 rules = auto-quarantine. That's per-agent detection with a swarm label.
9. **Detection never runs for live agents.** Only `/api/demo/run` and the GETs call the detector. Agents hitting the HTTP gateway are never analysed.
10. **N+1 queries.** `collaboration_approved` does `find_one` per write/read pair; `/api/graph` does `find_one` per evidence event. On Atlas at about 80 ms per round trip, this is why GETs were slow.
11. **Tenant filters missing** in `/api/episodes/{id}` (events and effects fetched by `_id` only) and `/api/graph`. All GETs are unauthenticated and accept any `tenant_id`.
12. **Concurrency.** No lock around demo runs; `BatchingStore.flush` clears then inserts across collections in parallel; the scenario `_counter` is module-global. Two clicks at once can interleave.
13. **Operator secret is in page JS** (`story.html`, `cockpit.html`). Fine for a demo, but say so, or move it to an HttpOnly cookie behind `DEMO_MODE`.
14. **Agent Engine tool takes `agent_id`/`task_id` as tool arguments**, so the model picks its own identity. `agent.yaml`'s entrypoint doesn't match `app.py`.
15. **Every agent has `export_data` approved and executes it on its own resources**, with no extra gate for high-impact tools beyond the resource list.
16. **Artifact content is never analysed.** The S2 note literally names the protected dataset. A deterministic out-of-scope-mention signal (R7) is cheap and needs no LLM.

## C. Evaluation and claims

- **"60 seeded runs, TP 50 / FP 0 / FN 0"** is 6 deterministic scenarios each run 10 times with no seed or variation: 6 data points, repeated. A judge who opens `benchmark.py` sees this immediately. Replace it with a randomized, seeded generator that includes hard negatives, and report what it actually finds, misses included.
- **The baseline is a strawman.** `baseline_detect` only flags denied tool calls, so "baseline misses S3" is guaranteed by construction. A per-agent baseline that flags each unauthorized access *does* catch S3's agents individually. The honest, stronger claim: "per-agent monitoring gives N unlinked alerts with no root cause or containment set; Swarmtect gives one incident, the root note, and the right agents."
- **S6 "real LangGraph agents"** are single-node graphs executing pre-written requests. Say "real LangGraph runtime, scripted steps".
- **Doc drift:** DEMO_SCRIPT says Vector Search activates "once wired"; STATUS says verified on Atlas. DESIGN_HANDOFF lists rules R1–R4+R6; DEMO_SCRIPT lists R2–R4+R6.

## D. What's genuinely good (keep it)

- The trust-tier split (gateway `authoritative` vs agent `self_reported`) and R5's "the record wins".
- Truth labels are stripped before events are stored, with a test proving it.
- Blocking happens before the effect, with a ledger receipt (`executed: false`, zero ledger rows).
- The negative control (S1) and the cross-tenant scenario (S5) exist at all; most teams skip both.
- STATUS.md's verified-vs-pending discipline.
- The guided UI: plain-English steps, staged reveal of *real* events, evidence one click away.

## E. Strategic note for the pitch

The biggest win available today isn't a new feature. It's turning section A into a demo beat: **"We attacked our own system. Here are 10 attacks, and here's each one caught."** (UI item U5, `/api/redteam/run`.) Most teams only show the happy path, and this shows the system held up against attacks you aimed at it on purpose. It also pre-empts the exact questions a technical judge would otherwise ask.
