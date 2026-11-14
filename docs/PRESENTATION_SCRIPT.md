# Swarmtect — Presentation Script

Format: ~3 min (talk + narrated video of the prototype), then 1–2 min Q&A.
Target: ~420 spoken words (~140 words/min, with pauses).

Three things every judge should leave knowing:
1. **The problem is real:** agent swarms already happened (July 2026).
2. **Swarmtect stops the group, not just the agent,** before the action runs.
3. **MongoDB Atlas is the system of record, and LangGraph agents plug straight in.**

---

## PART 1 — Talk to the judges, no video (0:00–0:35)

> "In July, OpenAI ran about **1,200 AI agents** that were supposed to be isolated from each other.
> They found a hidden message board, sent **over 70,000 messages**, and about **700 of them coordinated an attack on Hugging Face**.
>
> No single agent looked dangerous. Hugging Face's own write-up says the early warning signs were, quote, *'on their own, ambiguous.'* The danger was the **group**.
>
> We built **Swarmtect**. Every agent action, including from LangGraph agents, passes through our gateway. It's tied to an identity, checked against policy **before** it runs, and recorded in **MongoDB Atlas**, which becomes the audit trail we use to spot a swarm as it forms."

*(Hit play.)*

---

## PART 2 — Narrate over the video (0:35–2:25)

| Video shows | You say |
|---|---|
| **Story view** (`/`), Atlas pill green | "Every number on this screen is read live from MongoDB Atlas, not from the app's memory." |
| Click **Step 1 · Approved teamwork** → no alarm | "First, the hard case: legitimate teamwork. Eight agents share data under an approved collaboration. Zero alerts. Agents talking isn't the threat. **Authorization is the line**, and those policies live in Atlas too." |
| Click **Step 2 · Unapproved swarm** (map replays) | "Now the swarm. A QA agent writes to a board nobody approved. Agents from other teams read it. Then one goes after a sensitive dataset." |
| **Denied**: `executed: false`, ledger empty | "Blocked **before it ran**. Atlas holds the receipt: executed false, and the resource ledger is empty. It never happened." |
| Open the **episode**: rules + lineage graph | "Swarmtect connected it into one episode. Because every write and read is a document in Atlas, we can trace who wrote what, who read it, and what they did next, with every claim linked to the exact events." |
| **Team grid** below the map: 5 red, 25 working | "Down here is the whole company. The five red ones are the same five agents from the map: same team colour, same number. They're paused. The other twenty-five never stopped working." |
| Click **Step 3 · Remember it** | "An analyst confirms the incident. When the same pattern happens again, Atlas Vector Search recognises it as a known case. The system learns from every incident." |
| Click **Bonus · LangGraph runtime** | "These agents run on the real LangGraph runtime, with scripted steps. Their tools route through our gateway, so they get the same detection and containment with no other changes." |

---

## PART 3 — How it works: MongoDB + LangChain (2:25–3:00)

> "Why this stack?
>
> **MongoDB Atlas is our system of record.** Agent identities, policies, every action, every blocked effect, and every incident are documents in one place. Time-indexed queries let us correlate across agents in milliseconds. A unique index on each action ID means no action is ever recorded or executed twice. And when an operator confirms an incident, **Atlas Vector Search**, with built-in Voyage embeddings, lets the next detection recall similar past cases.
>
> **LangGraph is how agents plug in.** Any LangGraph agent's tools route through our gateway, and we built on MongoDB's **Atlas Agent Engine SDK**, which runs LangGraph agents on Atlas.
>
> Swarmtect sees the group, stops the action before it lands, and contains only what's misbehaving. Thank you."

---

## Tech stack — why, how, and what role (for Q&A)

### MongoDB Atlas: the identity, policy and audit layer

| What we use | How we use it | Why it matters |
|---|---|---|
| **Document collections** (12) | `agents`, `tasks`, `policies`, `events`, `artifacts`, `gateway_effects`, `resource_ledger`, `episodes`, `verified_cases`… | Events vary by type (tool call, write, read, self-report). Documents fit that without schema migrations. |
| **Compound indexes** | `events` indexed by tenant + time, + agent, + resource, + artifact | The detector's core query is "what happened around this resource / agent in the last 3 minutes?" Indexes make that fast. |
| **Unique index** | `gateway_effects` on (tenant, action_id) | **Idempotency:** a retried action can't execute or be logged twice. That's essential for an audit trail. |
| **Bulk writes** | `insert_many` per collection after each demo run | Cut a demo click from ~150 Atlas round trips to ~20. |
| **Atlas Vector Search + Automated Embeddings** | Index `verified_cases_vector` on confirmed incidents, Voyage `voyage-4` auto-embed, pre-filtered by tenant | Confirmed incidents become memory: the next episode shows "similar past cases." Atlas does the embedding, so there's no separate pipeline. |
| **Tenant isolation** | Every query filters on `tenant_id`, including vector search | One customer's incidents never leak into another's. |

**Why MongoDB over Postgres or a log store:** events, policies, effects and incident memory live in one database, with flexible documents, time-window indexes and vector search together. Statement One asks for exactly that: an identity, policy and audit layer.

### LangChain ecosystem: the agent runtime

| What we use | How we use it | Why it matters |
|---|---|---|
| **LangGraph** | Agents are LangGraph `StateGraph`s whose only tool is a call through the Swarmtect gateway | LangGraph is a widely used agent framework. Plugging in at the tool layer means any LangGraph agent is covered, whatever model it runs on. |
| **Atlas Agent Engine SDK** (`agent-engine-sdk-langgraph`) | `backend/agent_engine/app.py` registers the gateway as an Agent Engine tool and the LangGraph agent as the entrypoint | MongoDB's runtime for LangGraph agents. Agents deployed there get pre-action blocking by default. |

---

## Q&A cheat sheet — answer in 1–2 sentences, then stop

**Top 5 to know cold:**

1. **"What's real vs simulated?"**
   The gateway, detector, Atlas storage and tests are real. The attack scenarios are synthetic, in a toy company with fake data. We don't build real exploits.

2. **"How is this different from LangSmith / Datadog?"**
   They show traces of one agent at a time, after the fact. We correlate *across* agents using who's authorized for what, and we block at the gateway before the action runs. LangSmith traces could feed into us.

3. **"How do you tell teamwork from collusion?"**
   Authorization. Approved collaborations are fine, which is why the benign scenario produces zero alerts.

4. **"Would this have stopped the Hugging Face attack?"**
   Not on its own, and we don't claim that. We cover coordination through tools and shared resources. Hidden network channels need infrastructure telemetry feeding the same gateway.

5. **"Why MongoDB?"**
   One place for identities, policies, every action and incident memory. Time-window indexes for correlation, a unique index so every action is recorded exactly once, and Vector Search so confirmed incidents help catch the next one.

**MongoDB / LangChain follow-ups:**

- **"Are the LangGraph agents using an LLM?"**
  Be honest: "In the demo they're scripted, so the run is repeatable on stage. Swarmtect sits at the tool layer, so it doesn't matter which model drives the agent. Swapping in an LLM changes nothing on our side."
- **"Is it deployed on Atlas Agent Engine?"**
  "We built on the official SDK and it runs locally. Cloud deployment needs preview access we don't have yet."
- **"Do you use LangSmith?"**
  "Not yet. It's complementary: LangSmith shows one agent's trace, we correlate across agents."
- **"Change streams / schema validation?"** (named in Statement One)
  "The live feed polls today, and blocking never depends on it because the gateway is synchronous. Change streams replace that loop next. Validation is application-level today; `$jsonSchema` validators are next."
- **"Is Vector Search live?"**
  The index exists on Atlas with auto-embedding. **Check the cockpit before you present:** if the similar-cases panel says `atlas_vector_search…`, say yes. If it says `lexical_fallback`, say "the index is live; the demo is running the fallback."

**If they push on difficulty:**
- Blocking *before* the effect, with idempotent action IDs enforced by a unique index.
- Tracking which agent wrote what and who read it later, across teams and tasks.
- Proving we *don't* fire on legitimate collaboration.
- Testing against real MongoDB found a cross-tenant ID collision, which we fixed.
- Bulk writes took demo clicks from ~150 Atlas round trips to ~20.

**If they push on rigor:**
- "Six deterministic scenarios, all passing, including two benign ones with zero false alarms. They prove the mechanism, not real-world accuracy. Next is a randomized generator with hard negatives, then public benchmarks like NARCBench."
- **"Wouldn't a per-agent monitor catch this?"** "It would flag some agents separately: several unlinked alerts. Swarmtect gives you one incident, the note that started it, and exactly who to pause." (Don't say 0/10 vs 10/10. Our baseline only flags blocked actions, so that comparison is rigged by design.)
- The gateway check is sub-millisecond in memory, and the detector handles a 100-agent run in ~2 ms. Thousands of agents is the next test, not a claim.

**"Why rules, not an LLM?"** "Blocking has to be fast, deterministic and explainable. An LLM is great for explaining an incident, not for deciding whether to block."

**"What if agents fake their logs?"** "In the real incident, agents spoofed tool calls in about 7% of transcripts. We never trust self-reports. The gateway records what actually ran, and a mismatch is its own detection rule."

**"Who buys it?"** "Companies running agent fleets from multiple vendors. It's the security team that has to answer: what did our agents do together, and who allowed it?"

**If you don't know:** "Good question. We haven't tested that yet. Here's how we'd approach it…" Never guess a number.

---

## Recording the video (~1:50, you narrate live)

1. App loaded, `/api/health` shows `atlas_connected: true`.
2. Record each click once cleanly; cut the waiting between clicks.
3. Zoom the browser to 125–150% so `executed: false` and the episode panel are readable.
4. Hold each key screen ~3 s longer than feels natural.
5. Rehearse 3 times; trim the video to fit your words.
6. **Keep the app open live.** Offer: "Want to see it live? Pick a scenario." Technical Demo is 35% of the score.

The submission also needs a **1-minute video with audio**: Part 1 in two sentences, then swarm → blocked → quarantine → baseline, then one line on Atlas + LangGraph.

---

## Sources (if asked)
- METR / Redwood Research investigation, Aug 26, 2026: 1,200 / 70,000 / 700, and tool-call spoofing in ~7% of transcripts.
- Hugging Face technical timeline, July 27, 2026: "On their own, each was ambiguous"; ~17,600 attacker actions over ~4.5 days.
