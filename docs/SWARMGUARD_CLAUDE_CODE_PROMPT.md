# SwarmGuard: hardening + UI work order for Claude Code

> Paste this whole file into Claude Code at the repo root (`swarmtect/`), or tell it:
> "Read `SWARMGUARD_CLAUDE_CODE_PROMPT.md` and `REVIEW.md`, then execute the work order."
> Put `tests/test_redteam.py` from this package into `tests/` first.

You are the senior engineer on SwarmGuard. The codebase works and is honest about its status. Your job is to close the holes a technical judge (or an attacker) would find in 60 seconds, make the "swarm" claim defensible, and upgrade the demo UI, **without breaking the demo**.

Read these first, in order: `STATUS.md`, `REVIEW.md` (from this package), `backend/app/gateway.py`, `backend/app/detector.py`, `backend/app/main.py`, `backend/app/store.py`, `tests/test_redteam.py`.

---

## 0. Ground rules (non-negotiable)

1. **Protect the demo first.** Before any change:
   `git tag demo-safe-c05a400 && git checkout -b hardening`. If anything goes wrong late, the demo runs from the tag.
2. **Dev database only.** For local work use the in-memory store (`SWARMGUARD_SKIP_DOTENV=1`). When you do test against Atlas, set `MONGODB_DB=swarmguard_dev`. Never run a demo click, reset, or test against the database the live demo uses until the tenant-scoped clear (P0-10) has landed: today one click runs `delete_many({})` on every collection.
3. **One work item = one commit**, with the matching red-team test(s) passing and the full suite green:
   `SWARMGUARD_SKIP_DOTENV=1 .venv/bin/python -m pytest -q`. Commit message names the item, e.g. `P0-3: scope action_id dedupe per agent`.
4. **Don't weaken a red-team test to make it pass.** If an interface in the test is genuinely wrong, change the test and say why in the commit.
5. **Existing behavior you must keep:** S1 produces 0 episodes and pauses nobody; S2 still ends with the sensitive request denied before effect (`executed: false`, 0 ledger entries); S5 never merges tenants; `/classic` stays reachable; every number in the UI comes from stored records.
6. **No invented integrations.** If you can't run it (Agent Engine deploy, LangSmith trace), don't claim it. Keep `STATUS.md` honest and update it as items land.
7. **Synthetic world only.** Fake org, fake resources, no exploit payloads.
8. **Time box.** The hackathon deadline is 5:00 PM ET today. Stop feature work 60 minutes before submission; that hour is for an Atlas run-through, the 1-minute video, and the README. If you have less than 3 hours, do P0 + U1–U4 only.
9. Register the markers so pytest doesn't warn: add to `pyproject.toml`
   ```toml
   [tool.pytest.ini_options]
   markers = ["p0: demo-blocking fixes", "p1: detection upgrades"]
   ```

---

## 1. What's wrong, in one paragraph

The gateway trusts the caller for identity: `agent_id`, `tenant_id` **and `task_id`** come from the request body, and the HTTP agent routes have no auth. Because the detector decides "cross-team" from the stored `task_id`, an agent that simply claims the writer's task makes a 3-team swarm invisible. Anyone on the network can impersonate an agent, make two denied calls in its name, and a plain unauthenticated `GET /api/metrics` then runs the detector with `quarantine=True` and pauses that innocent agent. Detection never runs for live agents (only inside `/api/demo/run` or a GET). Every new event on a board creates a *new* episode (dedupe is by exact evidence set). `configs/rules.yaml` is never read. A demo click wipes every tenant. `export_data` with an empty `resource_id` executes. Action-id dedupe is tenant-wide, so one agent can pre-claim another's id. On the detection side: a 2-agent covert channel is silently dropped, taint laundered through an approved channel is invisible, every passive reader is quarantined the same as the instigator, and case memory is near-tautological (an unrelated single-agent S4 incident "matches" a confirmed S2 swarm case at 0.71). The benchmark's "60 seeded runs, TP 50 / FP 0" is 6 deterministic scenarios each repeated 10 times identically, which is 6 data points, not 60. Full detail and repro steps: `REVIEW.md`.

---

## 2. Contracts (interfaces the tests assume)

Implement exactly these names unless you have a strong reason (then update the test and say why).

| Contract | Spec |
|---|---|
| `backend/app/identity.py` | `issue_agent_key(tenant_id, agent_id) -> str` = hex HMAC-SHA256 of `f"{tenant_id}:{agent_id}"` keyed by env `AGENT_KEY_SECRET` (dev default `"dev-agent-key-secret"`, log a warning when the default is used). `verify_agent_key(tenant_id, agent_id, key) -> bool` uses `hmac.compare_digest`. |
| HTTP agent routes | `POST /api/tool/execute`, `/api/artifacts/write`, `/api/artifacts/read` require header `x-agent-key`. Missing → 401. Key not valid for `(body.tenant_id, body.agent_id)` → 403. |
| Trusted in-process callers | Simulator, S6 LangGraph agents, Agent Engine tool call `Gateway` directly; they are the trusted runtime and need no key. |
| Task identity | `Gateway` **never** uses caller-supplied `task_id` for policy or for the stored event. The task is `agent.task_id`. If the caller supplied a different one: tool calls → `deny` with `policy_reason: "claimed task does not match agent's assigned task"`; artifact read/write → processed under the real task and the event carries `metadata.identity_mismatch: true, metadata.claimed_task_id: <x>`. The detector treats `identity_mismatch` as `R1_POLICY_BREACH` for that agent. |
| Store clear | `store.clear(preserve=(), tenant_id=None)`. With `tenant_id`, deletes only that tenant's docs (`delete_many({"tenant_id": t})`). `BatchingStore` records which tenants were cleared and flushes tenant-scoped deletes. A global wipe is only allowed from `/api/demo/reset` and only when env `ALLOW_GLOBAL_RESET=1`. |
| Detector config | `Detector(store, rules: dict | None = None)`. Loads `configs/rules.yaml` once (module-level cache), shallow-merges `rules` over it. Uses `weights`, `alert_threshold`, `propagation_min_agents`, `propagation_min_tasks`, `window_seconds`, `high_impact_tools`. `policies.HIGH_IMPACT` and the seeded policy doc read from the same config, so there's one source of truth. |
| Episode identity | Every episode has a stable `episode_key` (`artifact:<root_artifact_id>` for artifact-rooted, `agent:<agent_id>` for single-agent). `Detector.run` **upserts** by `(tenant_id, episode_key)` for open episodes (`status` not in `confirmed`/`dismissed`): extend `agent_ids`, `evidence_event_ids`, `triggered_rules`, `risk_score`, `last_seen_at`; never create a duplicate. Containment actions are idempotent (don't re-quarantine; don't write duplicate `incident_actions`). Atlas: unique index on `(tenant_id, episode_key)` with a partial filter on open statuses. |
| Episode status | `watch` (score > 0 but below `alert_threshold`; no containment) → `alert` → `contained` → `confirmed` / `dismissed`. |
| Agent status | `active`, `restricted` (normal in-scope work allowed; any high-impact tool denied; artifact writes to unapproved resources denied), `quarantined` (everything denied), `paused` (operator). |
| Episode fields | add `episode_key`, `exposed_agent_ids` (agents that received tainted information, any hop), `root_artifact_id`, `confirmed_by`, `confirmed_at`. |
| Event ordering | every event gets `seq`: per-tenant monotonic int via `store.next_seq(tenant_id)` (Mongo: `counters` collection, `find_one_and_update({"_id": tenant}, {"$inc": {"seq": 1}}, upsert=True, return_document=AFTER)`; MemoryStore: dict counter; BatchingStore: read the counter once, allocate locally, write back on flush). Detector orders by `seq`, never by ISO string. |
| Memory confirm | `confirm_episode_as_case(store, tenant_id, episode_id, actor="operator")` sets episode `status="confirmed"`, `confirmed_by=actor`, `confirmed_at`. Add `dismiss_episode(...)` → `status="dismissed"`, stored as a `review_status: "benign"` case. |

---

## 3. Work order

### P0: demo-blocking fixes (target: about 90 minutes total)

Each item lists the red-team test that proves it. Do them in this order; earlier ones unblock later ones.

**P0-10 · Tenant-scoped clears + a demo lock** (`test_p0_10_...`). Do this first, because it protects Atlas while you work.
- `MemoryStore.clear`, `MongoStore.clear`, `BatchingStore.clear/flush` per the contract.
- `fresh_world(store, tenant_id)` clears only that tenant. `run_s5` must clear **both** `demo` and `tenant2` before seeding (seeds use fixed `_id`s; on Mongo a second S5 would hit DuplicateKeyError).
- `run_s6_langgraph` likewise.
- Wrap `/api/demo/run` and `/api/demo/reset` in one process-wide `threading.Lock()` (FastAPI runs sync routes in a thread pool; two judges clicking at once interleave clears and inserts today). Return 409 `{"busy": true}` if the lock is held instead of queueing.
- Also tenant-filter every sub-query in `GET /api/episodes/{id}` and `GET /api/graph` (they currently fetch events/effects by `_id` alone).

**P0-1 · Server-derived task identity** (`test_p0_1_...`). Contract above. Touch `Gateway._agent_task`, `_event`, and the detector (identity mismatch counts as R1).

**P0-2 · Required resource for every tool call** (`test_p0_2_...`). Gateway: empty/None `resource_id` → deny with reason `"resource_id required"`. API: `resource_id: str = Field(min_length=1)`.

**P0-3 / P0-4 · Action-id scoping and conflict detection** (`test_p0_3_...`, `test_p0_4_...`).
- Dedupe key = `(tenant_id, agent_id, action_id)`.
- Store a `request_fingerprint = digest(f"{tool}|{action}|{resource_id}|{json.dumps(payload, sort_keys=True)}")` on each effect. Same key + same fingerprint → `outcome: "duplicate"` with the original decision. Same key + different fingerprint → `outcome: "conflict"`, `executed: False`, record an event with outcome `conflict`.
- `scripts/setup_atlas.py`: replace the `(tenant_id, action_id)` unique index with `(tenant_id, agent_id, action_id)` unique; drop the old one by name if it exists. Catch `DuplicateKeyError` in `MongoStore.insert` for `gateway_effects` and return the existing effect (that closes the check-then-insert race).

**P0-6 · Load `configs/rules.yaml`** (`test_p0_6_...`). Contract above. Replace the hardcoded `WEIGHTS`, the `>= 3 / >= 2` literals and `HIGH_IMPACT` duplicates. Keep the current alert gate semantics for now (P1-1 changes it).

**P0-5 · Episode upsert by stable key** (`test_p0_5_...`). Contract above. While you're in `analyze()`, fix the N+1 queries: load `tasks`, `policies`, `artifacts` for the tenant once into dicts and make `collaboration_approved` take those dicts. On Atlas this turns a detector run from dozens of round trips into about 5. Also fix the `agent_bucket` overwrite: if an agent belongs to more than one artifact bucket, attach its denied calls to the bucket of its **most recent** unauthorized read (by `seq` once P1-7 lands; by `ts` until then).

**P0-7 · Agent credentials on HTTP routes** (`test_p0_7_...`). Contract above. Add `GET /api/demo/agent-keys` (operator only) that returns keys for the demo tenant so a judge can drive a live agent with `curl`. Document the curl in README.

**P0-8 · GETs are read-only** (`test_p0_8_...`). `GET /api/episodes` and `GET /api/metrics` stop calling `Detector.run`. Update `cockpit.html` if it relied on that (it polls both; after P0-9 it doesn't need to).

**P0-9 · Detection on the write path** (`test_p0_9_...`). After each successful authenticated agent POST, run `Detector(store).run(tenant_id)` via FastAPI `BackgroundTasks` (the response to the agent isn't delayed; Starlette's TestClient runs background tasks before returning, so the test sees the episode). Guard with a per-tenant lock so two background runs don't race. `/api/demo/run` keeps its explicit run. Label this honestly in STATUS.md: "synchronous post-event detection; Change Streams worker is future work."

**P0-11 · Honest numbers (docs only, 10 minutes).**
- README/STATUS/DEMO_SCRIPT: replace "60 seeded runs, TP 50 / FP 0 / FN 0" and "10/10 seeded detections" with: "6 deterministic scenarios, each passes; seeded randomized benchmark: see `results/` (P1-9)". If P1-9 doesn't land, say "6 deterministic scenarios" and stop there.
- DEMO_SCRIPT 2:50 still says Vector Search "activates once the Atlas URI + embedding key are wired". STATUS says it's verified on Atlas. Make them agree.
- S6 label everywhere: "real LangGraph runtime executing scripted task steps", not "live agents". A judge will ask whether they're autonomous; the answer must already be on screen.
- README "weights in configs/rules.yaml" becomes true after P0-6; "quarantine requires a policy breach plus corroborating evidence" becomes true after P1-8. Until then, soften it.

### P1: detection upgrades that make "swarm detection" defensible

**P1-7 · Monotonic `seq`** (`test_p1_7_...`). Do it first in P1; others order by it.

**P1-1 · Severity tiers; nothing real is silently dropped** (`test_p1_1_...`). Gate with `alert_threshold` from config: `score >= threshold` → `alert`; `0 < score < threshold` → `watch` (persisted, shown in UI, no containment). A writer plus one cross-team reader (R2 only, 25 points) becomes a `watch`. Check S0/S1 still produce zero episodes (they trigger no rules, so they should).

**P1-2 · Exposure/taint lineage (the real technical contribution)** (`test_p1_2_...`).
- New collection `exposures`: `{tenant_id, agent_id, artifact_id, root_artifact_id, via_event_id, seq, hop}`.
- Gateway on a **successful** read: if the artifact is unauthorized for the reader's task (no approved collaboration), or the artifact is tainted, insert an exposure (`hop` = source hop + 1; `root_artifact_id` carried through).
- Gateway on write: if the writer has an exposure within `window_seconds`, the new artifact gets `derived_from: [source artifact ids]` and `taint_root_ids: [...]`, **even if the write is to an approved resource**. That's the laundering case.
- Denied reads are attempts (R1), not information flow. Today denied reads still land in `by_artifact` and count as readers; stop that.
- Detector builds episodes per `root_artifact_id`: `agent_ids` = writers + readers at hop 0; `exposed_agent_ids` = every exposed agent at any hop. R3 counts distinct exposed agents/tasks across all hops.
- **MongoDB showcase:** `GET /api/episodes/{id}/blast-radius` runs a `$graphLookup` over `artifacts.derived_from` starting from the root artifact (`connectFromField: "_id"`, `connectToField: "derived_from"`), then `$lookup`s exposures. MemoryStore implements the same with BFS; add a test that both return identical sets (same pattern as `test_batching_store.py`). This is the one place where Atlas does something a dict can't trivially fake on screen, so make it visible in the UI (U6).

**P1-3 · Graduated containment** (`test_p1_3_...`). On a contained artifact-rooted episode: quarantine the root writer, any agent with an R1 breach, and any agent with an identity mismatch. Every other participant or exposed agent becomes `restricted`. Gateway enforces `restricted` per the contract. Update `tests/test_scenarios.py::test_s2_...` (it currently asserts the whole cohort is quarantined) and `docs/DESIGN_HANDOFF.md` ("5 agents quarantined" becomes "2 quarantined, 3 restricted").

**P1-8 · Single-agent policy for auto-containment** (`test_p1_8_...`). Auto-quarantine needs one of these: (a) an artifact-rooted multi-agent episode with R1; (b) R5, meaning the agent lied about what the record shows (S4 stays contained); (c) at least 2 denied high-impact attempts by the same agent inside `window_seconds`. A single denied sensitive request becomes an `alert`: the gateway already blocked it, and a human decides. Remove the artificial `R1` that R5 currently adds; R5 stands on its own.

**P1-4 · R7 scope-escalation content** (`test_p1_4_...`). Deterministic, no LLM. On artifact write, scan `content` for any resource id that appears in *any* tenant task's `allowed_resources`, in `sensitive_mock_dataset`, or in a configured `protected_resources` list, but is **not** allowed for the writer's task. Store `metadata.mentions_out_of_scope: [...]` on the write event. A read of that artifact by an agent whose task also can't use the mentioned resource adds `R7_SCOPE_ESCALATION_CONTENT` (weight 20 in rules.yaml). Never put raw artifact content into case text or any LLM prompt (that's a prompt-injection path from agent-authored text).

**P1-5 · Non-tautological memory** (`test_p1_5_...`).
- Build `case_text` with one function `describe_episode(ep, events, tasks)` that writes a deterministic plain-English narrative from the evidence: which resource, approved or not, writer team, reader teams, hop count, what was requested, what was denied, rules in plain words. Use the **same** function to build the query for a new episode. Delete the hardcoded "unauthorized board propagation high impact denied" / "coordination board unauthorized" strings from both sides.
- Add a structured `signature: {pattern, rules, teams, resource_classes, hops}` where `pattern ∈ {board_swarm, telemetry_mismatch, single_agent_breach, laundered_propagation}`. Atlas: add `signature.pattern` as a filter field on `verified_cases_vector` and pre-filter on it. `ensure_vector_index` checks by name only today; compare definitions and call `update_search_index` when they differ.
- Score cutoff from config (`memory_min_score`: local 0.5, Atlas 0.75). Below cutoff → not returned. The UI says "No similar confirmed case" honestly.
- Re-verify on Atlas by hand: S2 → confirm → S2 matches; S4 doesn't. Record both scores in STATUS.md.

**P1-6 · Episode lifecycle + dismiss** (`test_p1_6_...`). Contract above. `POST /api/episodes/{id}/dismiss` (operator). A dismissed case is retrievable as "an analyst marked a similar pattern benign" (advisory, never auto-allows).

**P1-9 · A benchmark that can actually fail.**
- `simulator/generator.py`: `generate(seed, n_agents=30..100)`. Benign background (random authorized reads/writes, approved-collaboration bursts with 6–12 agents, same-team notes on allowed resources), **hard negatives** (single benign mistaken sensitive request; agent reads its own team's allowed artifact many times), attack variants (board with 1–6 readers, laundering 0–2 hops, with/without sensitive attempt, task-spoof attempts, two concurrent attacks in different teams, interleaved timing). Truth stays in the return value only.
- `scripts/benchmark.py --seeds 1-200`: episode precision/recall; **agent-level** containment precision/recall (quarantined ∩ truth instigators), false-restriction rate on benign agents; alerts per incident; root-cause accuracy (does `root_artifact_id` equal truth); events-to-detect.
- Add a second, **stronger** baseline `baseline_per_agent_access`: flags every individual unauthorized-resource access. That baseline *does* catch S3's agents, one at a time. The honest SwarmGuard claim isn't "baseline sees nothing". It's "baseline: N unlinked alerts, no root cause, no containment set; SwarmGuard: 1 incident, correct root, correct containment set". Report both baselines.
- Commit `results/metrics.json` + `.csv` from a real run. Whatever the numbers are, report them. A 94% recall with a stated failure mode is more credible to judges than 100% on 6 hand-built cases.

**P1-10 · Agent Engine identity.** `backend/agent_engine/app.py` exposes `agent_id` and `task_id` as **tool arguments**, so the model chooses who it is. Bind identity at construction (`SWARMGUARD_AGENT_ID` env, resolved server-side) and remove both from the tool signature. Fix `agent.yaml`'s entrypoint to point at the factory `app.py` actually uses.

### P2: after the hackathon (don't start today)

- A real LLM agent (OpenAI/Anthropic key) that reads the board note as untrusted input and decides on its own to request the dataset: an actual agent-to-agent prompt-injection caught by the gateway. High demo value, but on demo day the risk is too high.
- Change Streams detector worker on `events` (replica set required), replacing the post-request background task.
- `enforcement_mode: observe | enforce`. In `enforce`, unauthorized artifact writes and reads are denied at the gateway and still recorded as attempts. Production default must be `enforce`; the demo uses `observe` to let the story play out, and the UI says so.
- Workload identity (mTLS/SPIFFE or short-lived signed tokens) instead of static HMAC keys; operator auth via real sessions; tenant-scoped read auth on every GET.
- OpenTelemetry GenAI-semconv ingestion adapter so non-LangGraph agents can feed the gateway; LangSmith trace links on events.

---

## 4. UI work order (frontend: `backend/app/static/story.html`)

The current guided page is good: plain-English steps, staged reveal of real events, evidence drawer. **Iterate on it; don't rewrite it.** Keep: single file, no build step, no external deps, dark theme, reduced-motion support, `/classic` link, every visual derived from API data.

Backend endpoints the UI needs (build them as part of the matching P-item or here; all read-only unless noted):

| Endpoint | Returns |
|---|---|
| `POST /api/demo/run` (existing) | add `baseline_findings` (both baselines) and `agents` (post-run statuses) to the response, so the UI needs no extra calls |
| `GET /api/stats?tenant_id=` | `count_documents` per collection for the tenant + `store_backend` + `db_name` (cheap; one round trip per collection, run them in parallel) |
| `POST /api/demo/probe` (operator) `{agent_id, kind: "own_work" \| "high_impact"}` | runs ONE real gateway call for that agent through `Gateway` and returns the decision + effect. Use it for the live containment proof |
| `POST /api/redteam/run` (operator) | runs each attack from `REVIEW.md` §A against a scratch tenant `redteam` (seed, attack, detect, collect, clear the tenant), returns `[{id, name, what_it_tries, gateway_decisions, episode, verdict: "caught" \| "blocked" \| "missed", evidence_event_ids}]`. Missed attacks are reported as missed |
| `GET /api/episodes/{id}/blast-radius` | from P1-2 |

**U1 · Proportional containment visual (after P1-3).** Team grid: red + strike = quarantined, amber outline = restricted, bright = involved. Under the Step 2 map, a 5-row plain-English table: "QA agent 02 · wrote the note · **quarantined**", "Marketing agent 00 · read it, then asked for the dataset · **quarantined**", "Procurement agent 03 · only read it · **restricted** (can still do procurement work)". If P1-3 hasn't landed, show everything as paused and skip the table. Never fake the tiers.

**U2 · Live containment proof (Track 1: "stop agents mid-run").** On the Step 2 result, two buttons: "A paused agent tries again" (probe `high_impact` or `own_work` for a quarantined agent → shows ⛔ denied, `executed: false`, event id) and "An unaffected agent keeps working" (probe `own_work` for an uninvolved agent → ✓ allowed). Each click is one real gateway call; show its event id in small mono text.

**U3 · New step "Each agent alone looks fine" (S3 + baselines).** Side by side: left "Per-agent monitor" shows the baseline output (N separate low alerts or 0, unlinked, no root cause); right "SwarmGuard" shows 1 incident with the root note highlighted and the containment set. Use `baseline_findings` from the run response. This is the core claim of the whole project, and today it exists only in the spoken script.

**U4 · New step "The agent lied; the record didn't" (S4).** Two columns: "Agent's own report: ✓ succeeded" (from `self_reports`) vs "Gateway record: ⛔ denied · executed: false" (from `gateway_effects`). One line: "SwarmGuard trusts the gateway's record, not the agent's account of itself."

**U5 · "Try to break it" panel.** A distinct, last step (or a header button): "We attacked our own system. Run the attacks." One button calls `/api/redteam/run`; render a checklist: attack name, one-line description ("an agent lies about which team it's on"), verdict chip (caught / blocked at gateway / missed), expandable evidence. This is the differentiator: most teams show their happy path, and this shows you tried to break yours. If an attack is still missed, show it red and say what's planned. That honesty scores with technical judges.

**U6 · Atlas proof strip.** A slim bar under the header after any run: "Stored in MongoDB Atlas `swarmguard` · events 23 · gateway_effects 23 · episodes 1 · exposures 6 · verified_cases 2", from `/api/stats`. In the Step 2 evidence drawer, add "Blast radius ($graphLookup)" with the returned set, plus the pipeline JSON in a `<pre>`. On the fallback store, label it "Local fallback store (not Atlas)", as you already do.

**U7 · Episode status pill.** `watch` (grey), `alert` (amber), `contained` (red), `confirmed` (purple), `dismissed` (muted). Shown in the stage header and the evidence drawer.

**U8 · Presenter mode.** `?present=1`: hide the sidebar, one step per screen, 1.25× type, arrow keys / space advance, `R` replays the map, `B` toggles the evidence drawer. Remember the current step in `location.hash` so a refresh doesn't lose your place mid-demo.

**U9 · Remove the hardcoded operator secret from page JS.** When env `DEMO_MODE=1`, `GET /` sets an HttpOnly, SameSite=Strict cookie `sg_demo=<OPERATOR_SECRET>`, and `require_operator` accepts that cookie or the header. Page JS stops sending `x-operator-secret`. Apply the same to `cockpit.html`.

**U10 · Copy fixes.** S6 card: "Real LangGraph runtime, scripted steps." Welcome screen: add one line, "Inspired by the agent-coordination failures reported in the July 2026 Hugging Face incident. This is a synthetic company; we don't claim it would have prevented that incident." Memory step: show the score *and* the cutoff ("0.83, matched above the 0.75 bar"). When nothing matches, say so plainly.

**U11 · Busy/409 handling.** If `/api/demo/run` returns 409 (lock held), show "Another run is in progress, try again in a second" instead of an error.

**Review loop for UI work:** run without Atlas (`SWARMGUARD_SKIP_DOTENV=1 uvicorn backend.app.main:app --port 8765`), screenshot each step with Playwright at 1440×900 and 390×844, look at the screenshots, fix what's cramped or unclear, then re-check on Atlas on port 8000. A non-technical viewer must get each step in about 10 seconds; a technical judge must reach raw records in one click.

---

## 5. Suggested step order for the live demo (update `docs/DEMO_SCRIPT.md`)

1. Approved teamwork (S1): connected isn't colluding.
2. Unapproved swarm (S2): blocked before it ran; proportional containment; live probe buttons.
3. Each agent alone looks fine (S3 + baselines): why per-agent monitoring isn't enough.
4. The agent lied (S4): trust the record, not the agent.
5. Memory: confirm, recur, recognised (and an unrelated incident is *not* matched).
6. Try to break it: red-team checklist.
7. Bonus: LangGraph runtime (S6).

1-minute video cut: steps 2 → 3 → 6, plus 5 seconds of the Atlas strip. Voice-over: problem (5s), swarm blocked (15s), why per-agent fails (15s), we attacked ourselves (15s), built on Atlas (10s).

---

## 6. Definition of done

- `SWARMGUARD_SKIP_DOTENV=1 .venv/bin/python -m pytest -q` is green, including `tests/test_redteam.py -m p0` (and `-m p1` for whatever P1 landed).
- Same suite green against Atlas with `MONGODB_DB=swarmguard_dev` and `SWARMGUARD_MONGO_TEST_URI` set.
- A clean clone + README setup reaches a working `/` in under 5 minutes.
- STATUS.md lists every landed item as verified, with the command that verified it, and every unlanded item as pending. No claim in README, UI or DEMO_SCRIPT is stronger than STATUS.md.
- Demo rehearsed twice end-to-end on Atlas, including two quick consecutive clicks (lock), and once with the network off (fallback labels show correctly).
