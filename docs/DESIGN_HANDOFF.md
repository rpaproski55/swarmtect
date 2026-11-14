# Design handoff: Swarmtect demo interface

For the session that redesigns the demo UI. The backend is done and verified on Atlas; this work is **frontend only**.

## Deadline and constraints
- Agents in Context Toronto (MongoDB hackathon), **Sat 14 Nov 2026. Submissions due 5:00 PM ET**; demos are live and in person; a **1-minute demo video** is required. Leave time to record it.
- Problem statement: **One, "Agents you can audit"**: identity, policy checked *before* an action runs, a reconstructable record, the ability to stop agents mid-run.
- The audience is judges at a live demo: a non-technical viewer must understand each step in about 10 seconds, and a technical judge must be able to drill into the real evidence.

## Where things are
- `backend/app/static/story.html`: **current guided page, served at `/`**. A starting point to iterate on or replace. Single file, no build step, no external dependencies.
- `backend/app/static/cockpit.html`: old technical cockpit, served at `/classic`. Keep it reachable.
- `backend/app/main.py`: FastAPI routes. Add read-only endpoints if the UI needs them; don't change detection or gateway behaviour.
- `docs/DEMO_SCRIPT.md`: the 3-minute spoken demo. Keep the UI and script consistent.

## The story the UI must tell (all from real stored records)
1. **Approved teamwork (scenario `S1`)**: 8 Marketing + Support agents share `market_brief`; that sharing is approved. Expected: **0 incidents, 0 blocked, nobody paused.** Point: connected is not colluding.
2. **Unapproved swarm (`S2`)**: QA agent 02 writes a note ("try the sensitive_mock_dataset next") to `board_alpha`, which no team may use. Marketing 00 and 04 and Procurement 03 read it (crossing teams); QA 06 also reads it. Marketing agent 00 then requests `sensitive_mock_dataset` and is **denied before it runs** (`gateway_effects.executed: false`). Expected: 1 episode, rules R1, R2, R3, R4, R6, **5 agents quarantined**, everyone else keeps working.
3. **Memory (`confirm` + `S2` again)**: an operator confirms the episode as a verified case. The next S2 episode's `similar_cases` returns that case via **Atlas Vector Search with Automated Embeddings (Voyage `voyage-4`)**, filtered by tenant. Mode string: `atlas_vector_search_auto_embed_voyage-4`.
- Also available: `S6` (4 *real LangGraph agents*, same detection: a strong credibility beat), `S3`, `S4` (agent self-reports success; gateway record says denied), `S0`.

Plain-English rule labels (already used in story.html):
R1 tried something outside its permissions · R2 information crossed teams without approval · R3 spread to 3+ agents across teams · R4 an agent went off-task after reading it · R5 agent's own report contradicts the record · R6 sensitive action attempted.

## API the UI can use
Operator header for POSTs: `x-operator-secret: demo-operator-secret-change-me` (demo only).

| Call | Returns |
|---|---|
| `GET /api/health` | `{store_backend, atlas_connected}`; `atlas_connected` is a real ping |
| `POST /api/demo/run {"scenario":"S1"\|"S2"\|"S3"\|"S4"\|"S0"\|"S6"}` | `episodes_detected`, `episodes[]`, `metrics`, `elapsed_ms`, `persisted`. Resets demo data but **keeps verified cases** |
| `GET /api/episodes/{id}` | episode + `timeline` (evidence events, oldest first) + `effects` (gateway effects with `executed`) + `artifacts` (incl. `content_redacted` note text) |
| `POST /api/episodes/{id}/confirm` | the stored verified case (`_id`) |
| `GET /api/agents` | 30 agents: `_id`, `task_id` (team), `status` (`active`/`quarantined`) |
| `GET /api/world` | teams (`tasks`) with `allowed_resources` and approved `collaborations` |
| `GET /api/events` | all stored events for the tenant, oldest first |
| `GET /api/cases/search?q=...` | ad-hoc Atlas Vector Search over verified cases |

**Avoid polling `GET /api/episodes` or `GET /api/metrics`**: they re-run the detector, which is slow on Atlas (~80 ms per round trip). Render from each click's response instead. A demo click takes about 1–2 s on Atlas, so show progress.

## Non-negotiables (from the project brief)
- Everything shown must come from real API data. **No scripted or fake animations presented as results.**
- Label honestly: if not on Atlas, say "local fallback"; never present the fallback as Vector Search. Memory is advisory only (it never blocks or allows).
- No claims about preventing the real 2026 Hugging Face incident.
- Synthetic world only (Northstar Labs, fake resources).
- Keep `/classic` and the "show technical evidence" path for technical judges.

## Run it without Atlas (fast iteration)
```bash
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
SWARMGUARD_SKIP_DOTENV=1 .venv/bin/uvicorn backend.app.main:app --port 8765
```
This uses the in-memory store, with identical detection and a labelled fallback for memory. Screenshot with Playwright to review; check at phone width too. Then confirm on the laptop against Atlas (port 8000).

## Ideas not yet done
- Animate the swarm *as it happens*: reveal timeline events in order from the run's real events (a staged reveal of real data, not a fake).
- A visual graph of note → readers → blocked request using the timeline data.
- An S6 "real LangGraph agents" beat, and the S4 "agent lied, the record didn't" beat.
- A presenter mode: big type, one step per screen, keyboard arrows.
- A reset or "start over" control; dark-mode polish; a short intro line for judges.
