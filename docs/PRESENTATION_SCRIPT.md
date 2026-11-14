# Swarmtect — Live Presentation Script

**Format:** ~3 min. You talk, then play the demo video and **pause it at 5 points** to explain. Then 1–2 min Q&A.
**Flow:** Hook → What I built + why it matters → Demo (with pauses) → Tech stack → Close.
**Tone:** simple words, short sentences. Let the screen do the work.

---

## 1 · HOOK (no video, ~20s)

> "Last week at the Hinton Lectures, one warning stuck with me.
> The biggest AI risk might not be one rogue agent. It's **many agents coordinating** in ways nobody approved.
>
> And it's already happened. Agents that were meant to be isolated found a way to talk to each other, and together they attacked **Hugging Face**."

---

## 2 · WHAT I BUILT + WHY IT MATTERS (no video, ~20s)

> "So I built **Swarmtect**.
>
> Businesses are about to run hundreds of agents doing real work. Swarmtect watches what those agents do **together**. It catches a swarm while it's forming, stops the risky action before it happens, and pauses only the agents involved, so the business keeps running."

*(Press play.)*

---

## 3 · DEMO: play the video, pause at each point (~1:45)

### ⏸ Pause 1: after Step 1 shows "no alarm"
> "First, normal work. Marketing and Support agents share a document, and they're allowed to. **No alarm.**
> Agents working together isn't the problem. Doing it **without permission** is."

*(Play.)*

### ⏸ Pause 2: on the red BLOCKED box
> "Now something goes wrong. One agent posts a note on a board **nobody approved**. Agents from three different teams read it. Then one of them goes after **sensitive data**.
>
> Swarmtect **blocked it before it ran**. Not an alert after the damage. It never happened.
>
> Every agent action is checked and recorded in **MongoDB Atlas** before it runs: who did it, under what permission, and whether it actually happened. Agents can't edit that record, so it's an **audit trail you can trust**."

*(Play.)*

### ⏸ Pause 3: on the team grid (5 red agents)
> "This is the whole company: thirty agents. The **five in red** are the same five from the map above. Those are the only ones paused.
> The other **twenty-five keep working**. We stop the swarm, not the business."

*(Play.)*

### ⏸ Pause 4: after Step 3 "Remember it"
> "Once someone confirms the incident, Swarmtect **remembers it**.
> Confirmed incidents become memory. **Atlas Vector Search** recognizes the same pattern next time, even if it looks a little different."

*(Play.)*

### ⏸ Pause 5: after the Bonus LangGraph step
> "And this isn't just our simulator. Agents built in **LangGraph**, a real agent framework, run the same attack and get caught **the same way**, with no changes to the agents."

*(Stop the video.)*

---

## 4 · TECH STACK (no video, ~25s)

> "Quickly, how it works.
>
> **MongoDB Atlas** is the backbone. Every agent action is checked against its permissions and recorded there before it runs. That gives us a complete audit trail, and it's how we connect actions across agents into one incident. **Atlas Vector Search** is the memory that recognizes repeat incidents.
>
> **LangGraph** is how agents plug in. Any LangGraph agent's tools run through our gateway, so it's protected automatically."

---

## 5 · CLOSE (~10s)

> "As agents start running more of the business, someone has to watch what they do together.
> **Swarmtect: see the swarm, stop it early.** Thank you."

---

## Cheat card (glance at this on stage)

| Pause | One line to remember |
|---|---|
| 1 · Step 1 | Allowed teamwork, no alarm |
| 2 · BLOCKED | Unapproved board → sensitive data → blocked before it ran · recorded in Atlas = trusted audit trail |
| 3 · Team grid | 5 paused, 25 keep working |
| 4 · Step 3 | Confirmed incidents become memory · Vector Search spots repeats |
| 5 · LangGraph | Real framework agents, caught the same way |

**Before you go on:** app open with the Atlas pill green, video cued up, and offer judges a live click if time allows: "Want to see it live? Pick a step."

**Accuracy note:** that Hinton Lecture was given by Paul Christiano. Say "at the Hinton Lectures," not "Hinton said."

---

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
---

## Sources (if asked)
- METR / Redwood Research investigation, Aug 26, 2026: 1,200 / 70,000 / 700, and tool-call spoofing in ~7% of transcripts.
- Hugging Face technical timeline, July 27, 2026: "On their own, each was ambiguous"; ~17,600 attacker actions over ~4.5 days.
