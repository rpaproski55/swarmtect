# Handoff for the receiving Muse — Swarmtect

You are receiving a **working, tested codebase**, not a spec. Read `STATUS.md` first — it separates verified facts from pending items. Do not re-plan the architecture; extend what's here.

**What this is:** Swarmtect — Atlas-native detection/containment of unauthorized AI-agent swarm coordination, built for the Agents in Context Toronto (MongoDB) hackathon, Nov 14 2026. Core idea: the *coordination episode* (write → read → goal drift across agents/tasks) is the unit of detection; a trusted gateway blocks high-impact actions *before* effect; benign approved collaboration must never alert.

**Verified state at handoff (don't take this file's word — run the tests):**
- `RUNNER_MODE=aer .venv/bin/python -m pytest -q` → 19 passed when `SWARMGUARD_MONGO_TEST_URI` points at a real mongod; 18 passed + 1 skipped without it.
- Gateway (pre-action policy + quarantine, effect ledger), detector R1–R6, scenarios S0–S5 (deterministic simulator), S6 (4 real LangGraph agents), per-agent baseline comparison, verified-case memory loop, live cockpit at `GET /` (SSE + evidence graph), FastAPI operator controls.
- Real MongoDB: full scenario suite passes against local mongod 8.0.4 via `MongoStore` — the exact code path Atlas uses.
- Benchmark: `scripts/benchmark.py` → `results/metrics.json` (60 runs, TP 50 / FP 0 / FN 0 at handoff).
- Agent Engine: official `agent-engine-sdk-langgraph` App constructs locally (`backend/agent_engine/app.py`); cloud deployment NOT done.

**Pending — needs the humans' credentials, never invent them:**
1. Atlas cloud: set `MONGODB_URI` in `.env`, run `scripts/setup_atlas.py`, re-run tests with `SWARMGUARD_MONGO_TEST_URI=<atlas uri>`.
2. Agent Engine deployment: preview org + `agentengine` CLI auth.
3. LangSmith: `LANGSMITH_API_KEY` in `.env` for real trace URLs.
4. Vector Search: Voyage key + Atlas vector index on `verified_cases.embedding` (filter fields `tenant_id`, `review_status`). Until then memory search is a *labelled* local fallback — keep the label.
5. ElevenLabs (optional, last): spoken incident briefing.

**Rules that matter:** never put credentials in chat/code/logs; all adversarial behaviour is synthetic in a toy org — no real targets, no exploit payloads; agents' self-reports are untrusted, gateway records are truth; truth labels must never reach detector inputs; don't claim any integration works until you've run it.

**Run it:** see `README.md` (5-minute setup). Demo script: `docs/DEMO_SCRIPT.md`.
