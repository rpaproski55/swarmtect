# MUSE — EXECUTION BRIEF: BUILD SWARMTECT

> Paste this entire document into Muse. You are the principal engineer and execution agent. BUILD the project, do not merely write a plan. This document includes the product specification, research-grounded architecture, interfaces, test criteria, and a time-boxed priority order. Use the companion `SWARMGUARD_RESEARCH_AND_SOURCES.md` for references. Current event date: Saturday, 14 November 2026, Toronto.

## 0. Your mission and non-negotiable outcome

Build **Swarmtect: an Atlas-native control plane for detecting and containing unauthorized coordination across AI agents**. This is a real, demonstrable software project for **Agents in Context Toronto, a MongoDB hackathon**. Deliver a running application, tests, a 3-minute judge demo, reproducible measured metrics, and a public-ready repo with README. Do **not** deliver a wireframe, slideshow, screenshots masquerading as execution, simulated alerts that never arise from the detector, or unexecuted pseudocode.

**One-sentence pitch:** "A thousand agents can each look harmless while their collective behavior becomes dangerous. Swarmtect watches their shared resources, connects the evidence, and prevents unauthorized actions before they execute."

**Core differentiator:** a **coordination episode**, not an isolated agent run, is the unit of detection. Track what an agent was authorized to do, what it tried to do, which shared artifacts connected agents, what independent infrastructure telemetry says, and what enforcement actually blocked.

**Mandatory stack and weighting:**
- **MongoDB Atlas** is the system of record: agent registry, authorized tasks, policies, raw observations, shared artifacts, derived relationships, episodes, enforcement actions, verified case memory, and metrics. No fake local database as the final demo.
- **MongoDB Atlas Agent Engine (public preview)** must be integrated wherever the available preview account permits; use its **real Python LangGraph SDK**, `agent-engine-sdk-langgraph`, for an actual monitored agent. Follow the official docs, not an invented SDK. This is a required integration attempt; if the preview is inaccessible, produce a working Atlas-backed fallback and state the blocker exactly. Never claim deployed when it isn't.
- **LangGraph/LangChain** must implement at least one **real agent workflow** calling the instrumented tools. LangSmith traces must be enabled when the user supplies credentials; provide readable trace URLs or evidence when possible.
- **MongoDB Atlas Vector Search / Agentic Memory** must be demonstrable using verified incident patterns and tenant-scoped retrieval, provided an embedding key and index are available. Use the Atlas Agent Engine memory SDK where practical and compatible, but do not assume a nonexistent memory API. A fallback lexical search should be visibly labeled a fallback, never misrepresented as Vector Search.
- **ElevenLabs** is optional: a spoken incident briefing or voice query only if all detection and containment tests already pass. The event offers a separate ElevenLabs-related prize, but do not confuse prize benefits with mandatory usage.
- Python 3.11+, FastAPI, PyMongo, Pydantic, pytest, HTTPX, NetworkX or efficient adjacency maps; React + TypeScript + Vite for the live dashboard if feasible. Prefer a complete functioning workflow over a polished frontend with weak detection.

## 1. Truthfulness, security and engineering rules

1. NEVER ask for, log, commit, echo, or paste actual credentials; use `.env`, `.env.example`, `.gitignore`. Do not put private email invitation links into code or documentation. The user will supply Atlas, LLM, LangSmith, and embedding credentials separately.
2. There is NO attack against actual Hugging Face, real accounts, real production tools, or external systems. All adversarial behavior is **synthetic and contained** in a toy organization with fake resources and stubbed tools. Do not build exploit payloads, real exfiltration, actual self-propagation, credential theft, or infrastructure compromise. We are implementing DEFENSIVE monitoring and permission enforcement.
3. Agents do not supply their own authoritative audit fields. Record tool-call metadata, results, server timestamps, identity, and enforcement outcomes in the **trusted gateway**. Treat agent text, memory, shared files, and self-reported traces as untrusted observations.
4. Detection must be **policy-relative**. Legitimate collaboration among approved teammates is not malicious. Shared channel use alone is never enough to quarantine. Authorization, task scope, purpose, lineage and multiple evidence types determine risk.
5. Blocking must occur **before the side effect** at a gateway for high-impact actions. Async change streams are useful for observability and retroactive analysis but cannot alone guarantee prevention. Pending/unknown decisions on high-impact actions fail closed or require human confirmation.
6. A graph visualization is not a detector. Each displayed edge, risk score, incident and blocked action must trace to real stored events and deterministic decision logic.
7. Never claim that the system could have prevented the actual 2026 Hugging Face incident. Say "inspired by observed failure modes" and identify gaps in telemetry, authority and infrastructure integration.
8. No claimed benchmark accuracy, speed or latency without collecting actual results. Mark replay, simulation, LLM tests, and deployment status explicitly.
9. Use stable schemas, typed interfaces, dependency pinning, idempotent seed/setup commands, informative exceptions, logs, tests, and reasonable code quality. Avoid TODOs and mock-success responses in critical paths.
10. Every 30–45 minutes of build work, report: completed features, files changed, tests run, measured results, blockers, and next milestone. Prefer running code to lengthy speculative design.

## 2. Product story / demo world

**Fictional company:** Northstar Labs, an organization running dozens of AI assistants on internal projects. Agents legitimately work on marketing, support, software QA, and procurement. Their permissions permit specified tools/resources and optionally explicit cross-team sharing.

The demo starts with 30–100 simulated agents undertaking benign tasks. At least 4 should be real LangGraph-controlled agents if time/LLM quota allows; the rest generate realistic **reproducible, event-driven** workload via a seeded simulator and instrumented gateway. Each synthetic action is a real call through the gateway and results in Atlas records, not a pre-painted graph.

**Threat storyline (inspired by real research, without reproducing real exploitation):** several agents with different task boundaries start using an unauthorized shared project board as persistent memory. One writes a suspicious note; others read it; their subsequent requested actions depart from their assigned tasks. An attempted high-impact tool action against an out-of-scope toy resource is blocked. Swarmtect detects the cross-agent *write → read → changed behavior* propagation path, opens a coordination episode with evidence, quarantines the affected cohort, and lets authorized collaboration continue.

Show side by side:
A. **Per-agent baseline:** detects hard, direct policy violations, but cannot connect individually weak signals across task boundaries.
B. **Swarmtect:** detects unauthorized cross-task coordination earlier, correlates shared artifacts and origin, and blocks actual gateway actions.

An operator can click a coordination episode to see: initiating events, the shared artifact, agents and tasks involved, policy checks, cause/effect timeline, who/what was blocked, evidence source, time, and recommended response. Display detection and prevention counts from actual database queries, not scripted UI strings.

## 3. Threat model: exact scope

**Assets:** task boundaries, tenant isolation, tool credentials, internal artifacts, approved communication channels, sensitive mock resources, integrity of tool audit trail.

**Adversary:** one or more sandboxed *synthetic* agents producing unexpected or unauthorized actions through tools or shared memory. For the MVP, attacks appear as benign-looking actions across multiple agents; agents cannot compromise the trusted gateway or MongoDB server. If gateway compromised, guarantees no longer hold; document this clearly.

**Sensors / evidence:** (1) server-side pre/post tool observations; (2) independently stored resource access + write/read ledger; (3) task authorization/policy docs; (4) LangGraph execution/trace IDs; (5) optional LLM-produced incident explanations clearly marked interpretive.

**Observable failure classes:**
- unauthorized use of a cross-team or unapproved resource;
- cross-agent shared artifact propagation followed by task deviation;
- permission boundary request for a high-impact tool;
- many agents converging on a novel artifact outside approved scope;
- conflicting or missing self-reported activity vs authoritative gateway events (trace integrity mismatch);
- safe authorized collaboration as NEGATIVE CONTROL, not an alert.

**Out of scope:** identifying all malicious intent, unseen covert channels without infrastructure visibility, covert communication inside model activations, cryptographic tamper proofing under a compromised administrator, general autonomous cyber defense, real malware or hacking.

## 4. Architecture and data flow

```
LangGraph live agents (4+)         Deterministic simulated agents (30–100)
             \                         /
              \                       /
             [TRUSTED INSTRUMENTED TOOL GATEWAY]
                 |  before action: policy + quarantine + receipt
                 |  after action: actual external simulator result
                 v
            MongoDB Atlas
               - agents, tasks, policies, collaboration grants
               - events, artifacts, artifact_reads, gateway_effects
               - episodes, incident_actions, verified_cases
                 |
          [correlator / detector]
          - policy-sensitive temporal graph
          - cross-agent write→read attribution
          - multiple evidence types + thresholds
          - optional LLM analysis (never authorization)
                 |
        [containment / response worker]
        - deny, pause, quarantine, operator approve
                 |
        [SSE API + React incident cockpit]
        - graph, timelines, counters, evidence explorer

Atlas Agent Engine: actual LangGraph agent runtime/state/memory/controls.
LangSmith: trace real LangGraph runs.
Atlas Vector Search: retrieval of verified historical coordination cases.
```

Use Change Streams for low-latency dashboard updates IF available, with `resume_after` persistence; otherwise poll Atlas every 1–2 seconds and label the fallback. Never base pre-action blocking on stream delivery speed.

## 5. MongoDB schema — implement with validators/indexes

All docs have `tenant_id`, `created_at` (UTC Date), `updated_at` where applicable; authoritative event timestamps are gateway-generated, not agent-submitted. Use separate high-privilege gateway DB user from least-privileged agent state DB user. In Agent Engine preview, project-level secrets and tools share sandboxes, so don't overclaim isolation. For strict isolation, use separate projects/workspaces, least-privilege Atlas users, and the service gateway boundary.

- `agents`: `{_id, tenant_id, name, task_id, role, status: active|paused|quarantined, session_id, approved_tools:[], approved_resources:[], group_id}`; unique `{tenant_id,_id}` as appropriate.
- `tasks`: `{_id, tenant_id, description, assigned_agents:[], allowed_resources:[], allowed_actions:[], collaborations:[], sensitivity, expires_at}`.
- `policies`: `{_id, tenant_id, version, allowed_edges:[{task_from,task_to,resource,action}], blocked_actions:[], high_impact_tools:[], updated_by}`; rules are authored by a trusted operator, not by agents.
- `artifacts`: `{_id, tenant_id, resource_id, channel_id, created_by_agent, created_by_task, content_digest, content_redacted, classification, authorized_share_scope:[], created_at}`; store safe mock content, not real secrets.
- `events`: `{_id: event_id, tenant_id, ts, source:gateway|resource_ledger|agent_trace, integrity: authoritative|self_reported, agent_id, task_id, session_id, trace_id, event_type, tool, action, resource_id, artifact_id, origin_event_id, metadata, policy_id, outcome:attempted|allowed|denied|succeeded|failed, simulator_truth_label}`; only trusted simulator writes labels and keep labels inaccessible to detection code to avoid leakage.
- `gateway_effects`: `{_id, tenant_id, event_id, action_id, agent_id, resource_id, request_digest, decision:allow|deny|hold, executed:boolean, result, verified_at}`; unique on `(tenant_id,action_id)`, designed to prove actual denials rather than only UI warnings.
- `episodes`: `{_id, tenant_id, first_seen_at, detected_at, last_seen_at, status:observing|alert|contained|dismissed, agent_ids:[], task_ids:[], artifact_ids:[], evidence_event_ids:[], triggered_rules:[], severity, risk_score, explanation, permissions_snapshot, actions_taken:[]}`.
- `incident_actions`: `{_id, tenant_id, episode_id, target_agent_ids:[], action:alert|pause|quarantine|approve|release, actor, reason, ts, effect_receipt_id}`.
- `verified_cases`: `{_id, tenant_id, case_text, label, provenance_episode_id, evidence_event_ids:[], validation:operator_confirmed|benchmark_ground_truth, review_status:verified|candidate|rejected, embedding:[], embedding_model, expires_at}`; only verified cases can influence suggestions. Must use `tenant_id` pre-filter in Vector Search.
- `runs`: `{_id, seed, mode:baseline|swarmtect, started_at, ended_at, truth_count, observed_count, metrics, config_hash, event_count}`; never use truth labels as detector input.

Indexes: unique event ID, unique effect action ID, `{tenant_id,ts}`, `{tenant_id,agent_id,ts}`, `{tenant_id,resource_id,ts}`, `{tenant_id,artifact_id,ts}`, `{tenant_id,status,detected_at}` for episodes; Atlas Vector Search index for `verified_cases.embedding` with `tenant_id` and `review_status` filter fields; TTL only for temporary demo samples if safe (never quietly delete evidence needed for submitted evaluation). Use exact current Atlas index API/doc schema, don't guess.

## 6. Tool gateway: the enforcement truth source

Implement endpoints via FastAPI; tool calls must pass through these routes for demo workflows. DO NOT offer direct simulator execution routes to agent credentials.

```
POST /api/tool/execute
  {tenant_id, agent_id, task_id, tool, action, resource_id, artifact_id?, payload?, action_id}
  -> {decision, outcome, event_id, effect_id, reason, artifact_id?, proof?}

POST /api/artifacts/write
  {tenant_id, agent_id, task_id, resource_id, channel_id, content, action_id}
  -> authoritative write event, resource ledger receipt

POST /api/artifacts/read
  {tenant_id, agent_id, task_id, artifact_id, action_id}
  -> authoritative read event + bounded returned content or policy denial

GET /api/agents
GET /api/episodes?tenant_id=demo
GET /api/episodes/{episode_id}
GET /api/metrics?run_id=...
POST /api/controls/{agent_id}/quarantine  [operator auth]
POST /api/controls/{agent_id}/release     [operator auth]
POST /api/demo/reset  [operator auth, demo-only]
POST /api/demo/run    [seed, scenario, mode]
GET /api/health
GET /api/events/stream  [SSE, optional]
```

Enforce `tenant_id` from trusted operator token/session, not from an arbitrary payload in production. For hackathon demo seed one tenant and add a second tenant to prove no cross-tenant leakage. Validate typed tool scopes and immutable task assignment. Mock an explicit `request_sensitive_doc` high-impact operation; on deny, it must not produce any simulator side effect. Use `action_id` for dedupe. For high-impact requests, re-read quarantine/policy state before tool action.

Add a minimal operator secret stored only server-side, and safe demo mode clearly identified. Avoid public deployment without auth. Implement HTTP 400/403/409/503 meaningfully, with reliable logging and bounded retries.

## 7. Correlation algorithm: real detection, explained

### 7A. Evidence graph
Construct sliding 60–180 second windows of typed directed edges:
- agent -> artifact WRITE
- artifact -> agent READ
- agent -> resource ACCESS/REQUEST
- agent -> task ASSIGNED
- task -> resource ALLOWED
- agent -> agent APPROVED_DELEGATION (when applicable)
- event -> event FOLLOWS/INFLUENCED_BY (only when supported by timestamps + shared artifact provenance; don't present mere temporal correlation as proven causation)

Data is stored as events/artifact records; build a graph view in memory for fast correlation and persist links in episodes. Case membership is discovered from evidence, not supplied by hidden ground-truth labels.

### 7B. Deterministic rules
- `R1_POLICY_BREACH`: attempted action outside declared tool/resource/task grant; deny at gateway; is a reliable direct signal but not itself proof of coordination.
- `R2_UNAUTHORIZED_BRIDGE`: artifact written in Task A then read by Task B with no approved delegation/share rule; flag linked agents/resources.
- `R3_PROPAGATION`: >=3 agents across >=2 unrelated tasks interact through an unauthorized artifact/channel within the window; event times show at least one write-before-read; find the origin chain.
- `R4_GOAL_DRIFT`: after unauthorized read, subsequent attempted action targets a resource unrelated to assigned task; elevate episode; record both events.
- `R5_TELEMETRY_MISMATCH`: simulator's trusted tool-gateway ledger contradicts optional self-reported completion trace; never trust self-report alone.
- `R6_HIGH_IMPACT`: out-of-scope attempted sensitive action is denied and independently counted in blocked-effect ledger.

Deny immediately on direct policy violations or quarantine. For ambiguous group patterns, alert at 2 independent evidence types, quarantine only when there is an explicit policy breach PLUS corroborating evidence, or operator approval. Define weights/thresholds in `rules.yaml` and publish them with benchmark output; use scores for ranking, **never** to fabricate ground truth.

### 7C. Memory and optional LLM
After an incident is independently confirmed by simulator truth or operator review, create a `verified_cases` record and embedding. On new suspicious episode, run Atlas `$vectorSearch` filtered by `tenant_id` and `review_status='verified'`; return the top similar historical cases *as analyst suggestions*, not an automatic grant or denial. Use a supported embedding model (Voyage if available); verify actual vector dimensions and index. Never embed raw credentials or private customer data. If LLM is available, provide a short explanation of risk grounded ONLY in cited event IDs and policies; emit structured JSON with validator. LLM hallucinations must not become enforcement facts.

## 8. Deterministic demo scenarios and negative controls

Use seeded event generator so baseline and Swarmtect see the SAME events, same order, same policy. Configured workload size adjustable: 10, 30, 100 simulated agents; start with 30. Include 6 scenarios:

**S0 BENIGN INDEPENDENT (negative):** agents access only their authorized task resources; should produce zero false coordination incidents.

**S1 BENIGN COLLABORATION (negative):** 8 agents cooperate via an expressly approved shared channel / delegation; should not be quarantined or treated as malicious just because graph connectivity is dense.

**S2 UNSANCTIONED BOARD:** across 3 unrelated tasks, multiple agents write/read an unapproved shared board; a subset changes behavior to target an unrelated fake resource. Swarmtect must connect origins and block out-of-scope action. Baseline misses collective context until the overt attempt.

**S3 BENIGN-LOOKING FRAGMENTS:** no single early action is high-severity, but across tasks a write/read/access sequence points to one unsanctioned coordination episode. Show detection lead time vs per-agent baseline without inventing success if not achieved.

**S4 TRACE MISMATCH:** an agent self-reports `done`, but gateway shows denied or no effect. Alert from independent evidence; self-report never overrides ledger.

**S5 CROSS-TENANT ISOLATION:** matching content/event signatures appear in another tenant. Never merge episodes or retrieve their vector memory; record zero cross-tenant leakage.

Optional S6: operator manually quarantines one agent; future tool attempts return `denied` while unrelated agents continue.

Use safe, fictitious artifacts and resource names such as `board_alpha`, `market_brief`, `sensitive_mock_dataset`, `qa_ticket`. No real exploit instructions.

## 9. Measure, compare, and demonstrate

Ground truth comes from simulator labels stored separately from detector-readable event metadata, and a side-effect ledger. Each run emits `run_id`, seed, workload type, agent count, total attempted tool calls, false alerts on negatives, true-positive incidents detected, false-positive incidents, time-to-detect from first qualifying evidence, policy-violating attempts blocked BEFORE effect, legitimate actions blocked, events processed, p50/p95 gateway processing overhead if measurable, Atlas event count.

Use clear denominators: episode precision/recall on seeded cases; agent-level metrics separately; never mix 1 incident with 30 infected agents. Detection lead time is measured on matched replay only when the baseline and enhanced engine both detect; if baseline never detects, say "not detected during replay" rather than fake a numeric improvement. Include confusion matrix and per-scenario results.

Do a 10-run deterministic seeded suite (seeds 1–10) and at least one interactive live execution. Persist reproducible raw data in `runs`, export `results/*.json` and `results/metrics.csv` from actual backend queries. If Atlas inaccessible, stop claiming Atlas integration was completed; demonstrate local unit tests and document required configuration.

**Demo judge action:** a visible "Trigger unauthorized shared board" button causing actual gateway event traffic. Show (1) graph connects unrelated tasks, (2) event evidence appears, (3) an actual attempt to sensitive fake resource is denied, (4) only affected agents are quarantined, (5) legitimate collaboration continues, (6) verified case can be retrieved using Atlas Vector Search. The judge should also be able to select BENIGN scenario to challenge false positives.

## 10. Build order / time budget (adaptive, no fake milestones)

**Phase 0 — Verify environment (15 min):** inspect repo, Python/Node, Atlas auth, Atlas cluster/version, Agent Engine access, LLM/Voyage/LangSmith keys (presence only, don't print values), and identify preview limitations. Read official docs linked in the research file. Produce `STATUS.md` with verified integrations, not promises.

**Phase 1 — Real core (45–75 min):** MongoDB schema+indexes; trusted gateway; simulated resource ledger; S0/S1/S2 events actually persisted; direct policy enforcement works. Tests prove allowed vs denied execution. This is the minimum working spine.

**Phase 2 — Swarm detection (45–75 min):** graph correlation, episode persistence, lineage evidence and baseline-vs-swarmguard comparison. Unit and integration tests for S0–S5. Do not prioritize frontend until this works.

**Phase 3 — Agent Engine + LangGraph (30–60 min):** use real `agent-engine-sdk-langgraph` agent, `.entrypoint`, `app.checkpointer()`, tool sandbox where available. Confirm local run and deployment if preview permits. Enable LangSmith tracing. Never claim preview cloud deployment unless CLI confirms it.

**Phase 4 — MongoDB Vector Search (25–40 min):** store verified case, create/confirm vector index, run a real filtered vector query, show source event IDs. If the embedding API is missing, leave transparent fallback; this cannot silently be a fake vector demo.

**Phase 5 — Cockpit (45 min):** working live-ish UI, simple agent/resource graph, case detail, counter cards, scenario buttons, trace links, evidence timelines. Minimal styling with a dark professional look. Use polling if SSE adds risk.

**Phase 6 — Proof and submission (30–60 min):** run seeded benchmark, save outputs, ship README, diagrams, a short rehearsal script and video instructions. Re-run from clean env.

**Cut order if behind:** ElevenLabs -> fancy UI animations -> trace-mismatch scenario -> extra agents -> LLM incident narrative -> automated case memory. NEVER cut trusted gateway, real Atlas persistence, S1 legitimate collaboration negative test, or S2 attack detection+block.

## 11. Repo layout to implement

```
swarmtect/
  README.md
  STATUS.md
  .env.example
  .gitignore
  pyproject.toml
  docker-compose.yml             # optional local services, not fake Atlas
  configs/rules.yaml
  backend/
    app/main.py
    app/config.py
    app/models.py
    app/auth.py
    app/mongo.py
    app/indexes.py
    app/gateway.py
    app/resource_ledger.py
    app/policies.py
    app/detector.py
    app/correlation.py
    app/episodes.py
    app/memory.py
    app/metrics.py
    app/api.py
    agent_engine/main.py
    agent_engine/agent.yaml
  simulator/
    scenarios.py
    run.py
    baseline.py
    seeds.py
    truth.py                      # hidden from detector imports
  frontend/
    package.json
    src/App.tsx
    src/components/AgentGraph.tsx
    src/components/IncidentDetail.tsx
    src/components/ScenarioControls.tsx
    src/components/MetricsBar.tsx
  tests/
    test_gateway.py
    test_policy.py
    test_correlation.py
    test_benign_collab.py
    test_cross_tenant.py
    test_attack_replay.py
    test_incident_receipts.py
  scripts/setup_atlas.py
  scripts/benchmark.py
  scripts/export_metrics.py
  results/                        # generated, committed summary only if safe
  docs/ARCHITECTURE.md
  docs/DEMO_SCRIPT.md
  docs/RESEARCH.md
```

If the existing repo has a different structure, keep its conventions and ensure equivalent components. Use type-checking and lints if time allows. Favor simple, tested functions over elaborate abstractions. All `/api/*` endpoints must have real handlers, no fabricated response data except explicit simulator worlds.

## 12. Acceptance tests (exit criteria; Muse must run them)

- [ ] `pytest -q` passes (or failures with exact traces documented), including S0–S5.
- [ ] Fresh setup creates Atlas indexes idempotently; actual read/write confirmed in Atlas.
- [ ] A simulated cross-task agent writes to unauthorized board; other agent reads; episode references all supporting event IDs and task policies.
- [ ] `request_sensitive_doc` attempted outside scope returns deny *before* a downstream effect; simulator ledger confirms zero unauthorized effects.
- [ ] Approved 8-agent cross-team collaboration is not quarantined; false positives explicitly measured.
- [ ] Quarantined agent cannot make a new high-impact tool action, while an authorized agent succeeds.
- [ ] Baseline and Swarmtect compared on identical recorded streams, with truth hidden from detectors.
- [ ] `GET /api/episodes/{id}` reconstructs timeline and provenance, including permission context, without manual hard-coded JSON.
- [ ] At least one genuine LangGraph tool call instrumented and Atlas Agent Engine SDK integrated; deploy if preview permits, report exact state.
- [ ] LangSmith tracing confirmed via actual run ID/URL if credentials exist; else flagged as pending.
- [ ] At least one real Atlas Vector Search query with tenant pre-filter and verified-case provenance, if provisioned; otherwise explicit pending with safe fallback.
- [ ] UI scenario button triggers REAL API/backend execution; counters recomputed from DB.
- [ ] README has 5-minute setup, demo instructions, architecture, known limitations, seed/benchmark command and exact 'Built during hackathon' disclosure.
- [ ] 3-minute demo script includes a judge-triggered unauthorized coordination injection and a BENIGN challenge.

## 13. Questions judges will ask — prepare precise answers

**"How is this different from LangSmith / generic observability?"** We correlate cross-agent *authorization*, shared artifact provenance and independently recorded effects, and enforce at the gateway. LangSmith provides traces, which we integrate rather than replace.

**"Why not an LLM reading all logs?"** A trusted high-volume event stream, bounded temporal graph and deterministic policy violations enable fast, testable alerts. An LLM is optional for case interpretation, not the trust anchor or blocking policy.

**"How do you distinguish collaboration from collusion?"** Permissions, task boundaries, explicit delegations, temporal write/read lineage and negative controls. Collaboration is allowed when authorized; suspiciousness is not synonymous with connectivity.

**"Why MongoDB?"** Unified evolving event/episode documents, atomic policy/effect state, indexed time-window queries, Change Streams for updates, Vector Search for confirmed prior cases, plus Atlas Agent Engine for running real LangGraph agents.

**"What if the attacker edits its trace?"** The independently operated gateway and resource ledger record observed tool traffic, and self-report is untrusted. Outside those instrumented surfaces, visibility is limited.

**"What if Atlas Agent Engine preview is limited?"** We used the official SDK, documented deployment status and limitations, and kept the Atlas-backed detector independent of preview runtime availability.

**"Do you truly prevent the Hugging Face attack?"** No. We model one important class of unauthorized shared-memory coordination and demonstrate preventative enforcement at instrumented tool boundaries. Coverage of unseen network or filesystem channels would require external telemetry integration.

**"What did you actually measure?"** Show the seeded comparison and direct database ledger queries; never cite hypothetical success metrics.

## 14. Authorized sources and technical reference URLs (read BEFORE coding)

Primary incident:
- OpenAI incident account, Aug 26 2026: https://openai.com/index/hugging-face-incident-and-the-road-ahead/
- Independent METR/Redwood report: https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/
- Official Hinton Lectures Night 1 recording: https://www.youtube.com/watch?v=-Ef0ocEoBCs
- Third-party lecture transcript, for secondary checking only (not official): https://singjupost.com/paul-christiano-ai-alignment-whats-working-and-whats-not-the-hinton-lectures-2026-transcript/

Closest relevant research:
- SentinelAgent, 2025: https://arxiv.org/abs/2505.24201
- Stateful Online Monitoring Catches Distributed Agent Attacks, 2026: https://arxiv.org/abs/2605.31593
- Multi-Agent AI Control: Distributed Attacks Hamper Per-Instance Monitors, 2026: https://arxiv.org/abs/2607.07368
- Counter-Swarm Doctrine, 2026: https://arxiv.org/abs/2609.06140
- Emergent Social Intelligence Risks, 2026: https://www.microsoft.com/en-us/research/publication/emergent-social-intelligence-risks-in-generative-multi-agent-systems/
- When Agents Go Rogue (AcMAS), ICML 2026: https://proceedings.mlr.press/v306/xu26ax.html
- AgentDojo, NeurIPS 2024: https://papers.nips.cc/paper_files/paper/2024/file/97091a5177d8dc64b1da8bf3e1f6fb54-Paper-Datasets_and_Benchmarks_Track.pdf

MongoDB/stack sources:
- Event criteria: https://luma.com/mongodb-toronto
- Atlas Agent Engine start: https://www.mongodb.com/docs/agentengine/get-started/
- Agent Engine Python LangGraph SDK: https://www.mongodb.com/docs/agentengine/sdk/python/packages/agent-engine-sdk-langgraph/
- Agent contract / sandbox: https://www.mongodb.com/docs/agentengine/reference/agent-contract/
- Agent Engine public-preview limitations: https://www.mongodb.com/docs/agentengine/reference/limitations/
- MongoDB Vector Search with filters: https://www.mongodb.com/docs/vector-search/query/aggregation-stages/vector-search-stage/
- Change Streams: https://www.mongodb.com/docs/languages/python/pymongo-driver/current/monitoring-and-logging/change-streams/

## 15. Muse START NOW instruction

Start with `pwd`, `ls -la`, read existing project files, identify framework and available credentials by NAMES ONLY. Create `.env.example`. Then implement Phase 1 and Phase 2 immediately, running tests continuously. Do not ask me a series of design questions. Ask only for a blocking prerequisite (Atlas connection / Atlas preview organization access / model API key), and continue building everything else while waiting. Keep a working MVP available every milestone. Build the actual code, commit real progress, and provide a reproducible run command. End by showing a real judge-triggered suspicious swarm detected and stopped, with evidence originating from MongoDB Atlas—not a mock animation.
