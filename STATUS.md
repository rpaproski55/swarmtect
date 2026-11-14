# SwarmGuard — STATUS (verified, not promised)

Updated: 2026-11-14, during Agents in Context Toronto hackathon build.

## Verified working
- Trusted tool gateway (FastAPI + core class): policy + quarantine checked **before** any simulator effect; denied high-impact actions produce a `gateway_effects` receipt with `executed: false` and zero `resource_ledger` entries.
- Detector R1–R6: policy breach, unauthorized bridge, propagation (≥3 agents / ≥2 tasks), goal drift, telemetry mismatch, high-impact denial. Episodes persist with real evidence event IDs.
- Scenarios S0–S5 as real gateway traffic, including benign collaboration negative control (S1) and cross-tenant isolation (S5).
- **S6: four real LangGraph agents** through the gateway (2 benign, 3-agent board swarm) — detected and contained identically to simulated agents.
- Baseline comparison: per-agent detector on the identical stream.
- **Real MongoDB code path**: full S0–S5 suite passes against a real local mongod 8.0.4 via `MongoStore` (the same code Atlas uses) — `tests/test_mongo_store.py` with `SWARMGUARD_MONGO_TEST_URI` set; `scripts/setup_atlas.py` index creation verified against it. Two real bugs were found and fixed this way (cross-tenant `_id` collisions; invalid unique `_id` index spec).
- **Verified-case memory loop**: contained episode → operator confirm → verified case → the *next* episode retrieves it as a similar case (local hash-embedding fallback, honestly labelled; Atlas `$vectorSearch` path in code for when provisioned). Case memory survives scenario resets by design and never crosses tenants.
- **Live cockpit** at `GET /`: counters, scenario buttons, evidence graph, episode timelines, SSE event stream (polling fallback, labelled) — all read from stored records, verified over HTTP.
- Tests: 19 passed with Mongo + Agent Engine env set (`pytest -q`).
- Benchmark v2 (`results/metrics.json`): 60 seeded runs, episode-level **TP 50 / FP 0 / FN 0**; gateway latency p50 0.156 ms / p95 0.207 ms (memory store — Atlas adds network RTT); 100-agent scale run: 106 events, detector 2 ms, attack episode detected.

## Pending / blocked on credentials (NOT claimed)
- **MongoDB Atlas (cloud)**: no `MONGODB_URI` supplied yet. The Mongo code path itself is proven against a real local mongod (above); Atlas adds only the connection string + network. Run `scripts/setup_atlas.py` once the URI is in `.env`, then the same tests run against Atlas.
- **Atlas Agent Engine (public preview)**: SDK VERIFIED locally 2026-11-14 — official `agent-engine-sdk-langgraph` 0.11.14 installed, real `App` constructed (RUNNER_MODE=aer), gateway tool + LangGraph entrypoint registered and test-covered (`tests/test_agent_engine_sdk.py`). Cloud **deployment is not claimed** — it requires preview org access + `agentengine` CLI auth + a real Atlas URI.
- **LangGraph**: VERIFIED 2026-11-14 — real LangGraph agent (`backend/agent_engine/main.py`) invoked through the gateway: allowed call executed, `request_sensitive_doc` denied with no effect. Covered by `tests/test_langgraph_agent.py`. Atlas Agent Engine SDK/deployment still separate and pending (below).
- **LangSmith**: no key supplied; tracing flags are in `.env.example`, no trace URL is claimed.
- **Atlas Vector Search**: `backend/app/memory.py` runs a real `$vectorSearch` only with a Mongo backend + embedding + index; otherwise it returns a **labelled lexical fallback**.
- **ElevenLabs**: not implemented (optional, cut first per brief).

## Safety scope
All adversarial behavior is synthetic, in a toy org (Northstar Labs) with fake resources (`board_alpha`, `sensitive_mock_dataset`). No real systems, accounts, or exploit payloads.
