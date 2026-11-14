# SwarmGuard — STATUS (verified, not promised)

Updated: 2026-11-14, during Agents in Context Toronto hackathon build.

## Verified working
- Trusted tool gateway (FastAPI + core class): policy + quarantine checked **before** any simulator effect; denied high-impact actions produce a `gateway_effects` receipt with `executed: false` and zero `resource_ledger` entries.
- Detector R1–R6: policy breach, unauthorized bridge, propagation (≥3 agents / ≥2 tasks), goal drift, telemetry mismatch, high-impact denial. Episodes persist with real evidence event IDs.
- Scenarios S0–S5 as real gateway traffic, including benign collaboration negative control (S1) and cross-tenant isolation (S5).
- **S6: real LangGraph runtime, scripted task steps** (4 agents) through the gateway (2 benign, 3-agent board swarm) — detected and contained identically to simulated agents.
- Baseline comparison: per-agent detector on the identical stream.
- **Real MongoDB code path**: full S0–S5 suite passes against a real local mongod 8.0.4 via `MongoStore` (the same code Atlas uses) — `tests/test_mongo_store.py` with `SWARMGUARD_MONGO_TEST_URI` set; `scripts/setup_atlas.py` index creation verified against it. Two real bugs were found and fixed this way (cross-tenant `_id` collisions; invalid unique `_id` index spec).
- **Verified-case memory loop**: contained episode → operator confirm → verified case → the *next* episode retrieves it as a similar case (local hash-embedding fallback, honestly labelled; Atlas `$vectorSearch` path in code for when provisioned). Case memory survives scenario resets by design and never crosses tenants.
- **Live cockpit** at `GET /`: counters, scenario buttons, evidence graph, episode timelines, SSE event stream (polling fallback, labelled) — all read from stored records, verified over HTTP.
- Tests: 19 passed with Mongo + Agent Engine env set (`pytest -q`).
- **MongoDB Atlas (cloud)**: VERIFIED 2026-11-14 — `scripts/setup_atlas.py` created indexes + the `verified_cases_vector` search index on Cluster0; full suite **19 passed against Atlas** (`SWARMGUARD_MONGO_TEST_URI` = Atlas URI, `RUNNER_MODE=aer`, Python 3.12); app on :8000 reports `/api/health` → `store_backend: mongodb-atlas, atlas_connected: true`.
- Scenario checks (`scripts/benchmark.py`): the 6 deterministic scenarios (S0–S5) each produce the expected result. Note: the runs are not randomized, so repeating them 10× is the same 6 data points, not 60 independent trials. A randomized seeded benchmark with hard negatives is future work. gateway latency p50 0.156 ms / p95 0.207 ms (memory store — Atlas adds network RTT); 100-agent scale run: 106 events, detector 2 ms, attack episode detected.

## Pending / blocked on credentials (NOT claimed)
- **Atlas Agent Engine (public preview)**: SDK VERIFIED locally 2026-11-14 — official `agent-engine-sdk-langgraph` 0.11.14 installed, real `App` constructed (RUNNER_MODE=aer), gateway tool + LangGraph entrypoint registered and test-covered (`tests/test_agent_engine_sdk.py`). Cloud **deployment is not claimed** — it requires preview org access + `agentengine` CLI auth + a real Atlas URI.
- **LangGraph**: VERIFIED 2026-11-14 — real LangGraph agent (`backend/agent_engine/main.py`) invoked through the gateway: allowed call executed, `request_sensitive_doc` denied with no effect. Covered by `tests/test_langgraph_agent.py`. Atlas Agent Engine SDK/deployment still separate and pending (below).
- **LangSmith**: no key supplied; tracing flags are in `.env.example`, no trace URL is claimed.
- **Atlas Vector Search**: `backend/app/memory.py` runs a real `$vectorSearch` only with a Mongo backend + embedding + index; otherwise it returns a **labelled lexical fallback**.
- **ElevenLabs**: not implemented (optional, cut first per brief).

## Safety scope
All adversarial behavior is synthetic, in a toy org (Northstar Labs) with fake resources (`board_alpha`, `sensitive_mock_dataset`). No real systems, accounts, or exploit payloads.

## Demo-click performance (2026-11-14)
- Measured on Atlas: ~80 ms per round trip; a demo click made ~150 sequential round trips (11–15 s).
- `/api/demo/run` now runs the click's gateway + detector workload against a run-scoped write-behind copy (`BatchingStore`) and persists it to Atlas in bulk (parallel clears + one `insert_many` per collection). Detection results are identical to the per-call path (`tests/test_batching_store.py`, S0–S4 + S6). Expected ~1–2 s per click; to be re-measured on Atlas. Response includes `elapsed_ms` and what was persisted.
- Live per-call paths are unchanged: `/api/tool/execute`, artifact routes, Vector Search.
- `/api/health` now pings Atlas instead of reporting configuration only.
- S2 fix: the sensitive request now comes from the Marketing agent that read the QA-written board (cross-task), so the episode carries R4 goal drift as the demo script describes.

## Hardening from external review (2026-11-14, branch `claude/great-babbage-x1nmiy`)
Red-team suite: `tests/test_redteam.py` (from `docs/REVIEW.md`). Verified with
`SWARMGUARD_SKIP_DOTENV=1 RUNNER_MODE=aer .venv/bin/python -m pytest -q` (in-memory store; not yet re-run on Atlas).
- **Landed (tests pass):** P0-1 server-derived task identity · P0-2 resource required · P0-3/4 per-agent action ids + conflict detection · P0-5 one board = one episode (upsert) · P0-6 `configs/rules.yaml` drives detection · P0-7 agent keys (`x-agent-key`) on HTTP agent routes · P0-8 GETs are read-only · P0-9 detection on the write path (post-request background task; Change Streams worker is future work) · P0-10 tenant-scoped clears · P0-11 honest numbers · P1-1 `watch` tier · P1-6 confirm records who/when · P1-7 per-tenant event `seq` · P1-8 a single agent's single blocked mistake is an alert, not a quarantine (R5 no longer adds a synthetic R1).
- **Pending (tests still fail, by design):** P1-2 taint/exposure lineage + `$graphLookup` blast radius · P1-3 graduated containment (restricted vs quarantined) · P1-4 R7 content signal · P1-5 non-template case memory · P1-9 randomized benchmark · P1-10 Agent Engine identity binding · `window_seconds` time window.
- **Atlas note:** run `scripts/setup_atlas.py` once to switch the `gateway_effects` unique index to `(tenant_id, agent_id, action_id)`.

