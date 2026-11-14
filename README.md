# SwarmGuard

**Atlas-native detection and containment of unauthorized AI-agent swarm coordination.**
Built during the Agents in Context Toronto hackathon (MongoDB), 14 Nov 2026.

> A thousand agents can each look harmless while their collective behavior becomes dangerous. SwarmGuard watches their shared resources, connects the evidence, and prevents unauthorized actions before they execute.

The unit of detection is a **coordination episode** — not an isolated agent run. SwarmGuard tracks what each agent was authorized to do, what it tried to do, which shared artifacts connected agents (write → read → changed behavior), and what the gateway actually blocked, in an independently recorded effect ledger.

## 5-minute setup

```bash
cd swarmtect
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"   # Python 3.11–3.14 (3.15 lacks openinference wheels)
cp .env.example .env        # add MONGODB_URI here for Atlas (loaded automatically); blank = labelled in-memory fallback
.venv/bin/python scripts/setup_atlas.py   # idempotent: indexes + Vector Search index (Atlas only)
.venv/bin/python -m pytest -q
```

## Run it

```bash
# API + live cockpit (open http://localhost:8000/ in a browser)
OPERATOR_SECRET=demo-operator-secret-change-me .venv/bin/uvicorn backend.app.main:app --port 8000
curl -X POST localhost:8000/api/demo/run -H 'x-operator-secret: demo-operator-secret-change-me' \
  -H 'Content-Type: application/json' -d '{"scenario":"S2"}'
curl localhost:8000/api/metrics

# Full suite incl. real-MongoDB integration (needs a mongod / Atlas URI)
SWARMGUARD_MONGO_TEST_URI=mongodb://127.0.0.1:27017 RUNNER_MODE=aer .venv/bin/python -m pytest -q   # 19 passed

# Seeded benchmark (10 runs/scenario) -> results/metrics.json + .csv
.venv/bin/python scripts/benchmark.py

# Atlas index setup (only with a real MONGODB_URI)
MONGODB_URI=... .venv/bin/python scripts/setup_atlas.py
```

## Scenarios
- **S0** benign independent work — negative control
- **S1** benign approved collaboration (8 agents) — negative control, must never quarantine
- **S2** unsanctioned shared board → propagation → high-impact attempt **blocked before effect**
- **S3** benign-looking fragments across tasks → one coordination episode (per-agent baseline misses it)
- **S4** trace mismatch — agent self-reports success, gateway ledger proves denial
- **S5** cross-tenant isolation — identical signatures in two tenants never merge
- **S6** real LangGraph runtime executing scripted task steps (4 agents, not the simulator), same gateway, detection and containment

## How detection works
Deterministic rules over gateway-authoritative events (weights in `configs/rules.yaml`): R1 policy breach, R2 unauthorized bridge, R3 propagation, R4 goal drift, R5 telemetry mismatch, R6 high-impact denial. Quarantine requires a policy breach **plus** corroborating evidence. An LLM is never the trust anchor or the blocking policy.

## Honest status
See `STATUS.md` — it separates verified integrations from pending ones (Atlas URI, Agent Engine preview deployment, LangSmith traces, Vector Search index). Nothing pending is claimed as done. The in-memory fallback is labelled as such everywhere it appears.

## Limitations
Coverage is limited to instrumented tool/shared-resource surfaces. Unseen network/filesystem channels, covert channels inside model activations, and a compromised gateway are out of scope (brief §3). SwarmGuard is *inspired by* failure modes of the July 2026 Hugging Face incident; it does not claim it could have prevented that incident.

Docs: `docs/ARCHITECTURE.md`, `docs/DEMO_SCRIPT.md` (3-minute judge script), `docs/RESEARCH.md`, `docs/MASTER_BRIEF.md`.
