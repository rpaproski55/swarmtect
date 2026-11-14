# SwarmGuard — Presentation Script

Format: ~3 min (talk + narrated video of the prototype), then 1–2 min Q&A.
Target: ~400 spoken words total (~140 words/min, with pauses).

---

## PART 1 — Talk to the judges, no video (0:00–0:35)

> "In July, OpenAI ran about **1,200 AI agents** that were supposed to be isolated from each other.
> They found a hidden message board, sent **over 70,000 messages**, and about **700 of them coordinated an attack on Hugging Face**.
>
> The scary part: no single agent looked dangerous. Hugging Face's own write-up says the early warning signs were, quote, *'on their own, ambiguous.'*
>
> Today's tools watch agents one at a time. The danger was the **group**.
>
> We built **SwarmGuard**: a gateway every agent action passes through. Every action is tied to an identity, checked against policy **before** it runs, and recorded in MongoDB Atlas, so we can see coordination as it forms and stop it."

*(Hit play.)*

---

## PART 2 — Narrate over the video (0:35–2:35)

| Video shows | You say |
|---|---|
| **Cockpit dashboard**, counters at zero | "This is our cockpit. Every number here is read live from Atlas." |
| Click **Run BENIGN collaboration**: 8 agents share a brief, **0 episodes** | "First, the hard case: legitimate teamwork. Eight agents across Marketing and Support share data under an approved collaboration. Zero alerts. Agents talking isn't the threat. **Authorization is the line.**" |
| Click **Trigger unauthorized shared board** | "Now the swarm. A QA agent writes to a board nobody approved. Agents from other teams read it. Then one of them goes after a sensitive dataset." |
| **Denied** — `executed: false`, ledger empty | "Blocked **before it ran**. The effect ledger is empty. This isn't an alert after the damage. It never happened." |
| Open the **episode**: rules fired, lineage graph | "SwarmGuard connected it into one episode: an unauthorized bridge, the information spreading across teams, an agent drifting off its task. Every claim links to the exact events behind it." |
| **Quarantine**: 5 agents isolated, others still working | "And we contain only the five agents involved. Everyone else keeps working. You don't shut down the whole company to stop one swarm." |
| Click **Fragmented coordination (S3)** + baseline comparison | "Here's why this matters. When the attack is spread thin, a per-agent monitor on the exact same data catches **zero out of ten**. SwarmGuard catches **ten out of ten**." |
| **4 real LangGraph agents (S6)** | "This isn't just a simulation. Real LangGraph agents run through the same gateway and get caught the same way." |

---

## PART 3 — Back to the judges, no video (2:35–3:00)

> "Under the hood: a synchronous gateway, six detection rules over a time window, a cross-agent lineage graph, and everything stored in Atlas. Confirmed incidents become memory for the next detection via Vector Search.
> Across 60 test runs: **every attack caught, zero false alarms.**
>
> Monitoring agents one at a time is table stakes. SwarmGuard sees the group, stops the action before it lands, and contains only what's misbehaving.
> Thank you. Happy to take questions."

---

## Recording the video (≈2:00, no audio needed — you narrate live)

1. Start with the app already loaded and `/api/health` checked.
2. Record each click **once cleanly**, cut the waiting time between clicks.
3. Zoom in (browser 125–150%) so judges can read `executed: false` and the episode panel.
4. Hold each key screen ~3 s longer than feels natural. You need time to talk over it.
5. Rehearse with the video 3 times; trim the video to fit your words, not the other way round.

**The submission also needs a 1-minute video with audio.** Use the same footage: Part 1 in two sentences, then the swarm → blocked → quarantine → baseline beats.

---

## Q&A cheat sheet — answer in 1–2 sentences, then stop

**Top 5 to know cold:**

1. **"What's real vs simulated?"**
   The gateway, detector, Atlas storage, tests and LangGraph agents are real. The attack is synthetic, in a toy company with fake data. We don't build real exploits.

2. **"How is this different from LangSmith / Datadog / observability?"**
   They show traces, one agent at a time, after the fact. We correlate across agents using who's authorized for what, and we block at the gateway before the action runs.

3. **"How do you tell teamwork from collusion?"**
   Authorization. Approved collaborations are fine, which is why our benign scenarios produce zero alerts. It's unauthorized sharing that crosses task boundaries and then reaches for something sensitive.

4. **"Would this have stopped the Hugging Face attack?"**
   Not on its own, and we don't claim that. We cover coordination through tools and shared resources. Hidden network channels need infrastructure telemetry feeding the same gateway. That's the roadmap.

5. **"Why MongoDB?"**
   Events, policies, effects and episodes are documents in one place, with time-window indexes for fast correlation, unique indexes so every action is recorded exactly once, and Vector Search so confirmed incidents become memory.

**If they push on difficulty:**
- Blocking *before* the effect with idempotent action IDs, not logging after.
- Tracking which agent wrote what, and who read it later, across teams and tasks.
- Proving we *don't* fire on legitimate collaboration (negative controls).
- Tenant isolation: testing on real MongoDB found a cross-tenant ID collision we fixed.
- Demo clicks went from ~150 Atlas round trips to ~20 with bulk writes.

**If they push on rigor:**
- "60 seeded runs we designed: they prove the mechanism, not real-world accuracy. Next is public benchmarks like NARCBench."
- Gateway check is sub-millisecond in memory; the detector handles a 100-agent run in ~2 ms. Thousands of agents is the next test, not a claim.

**If they ask "why rules, not an LLM?"**
"Blocking has to be fast, deterministic and explainable. An LLM is great for explaining an episode to a human, not for deciding whether to block."

**If they ask about agents faking their logs:**
"In the real incident, agents spoofed tool calls in about 7% of transcripts. We never trust self-reports. The gateway records what actually ran, and a mismatch is its own detection rule."

**If they ask about change streams / schema validation (named in Statement One):**
"The live feed polls today. Blocking never depends on it because the gateway is synchronous. Change streams replace that loop next, and `$jsonSchema` validators are next on schema."

**If they ask who buys it:**
"Any company running agent fleets from multiple vendors. It's the security team that has to answer: what did our agents do together, and who allowed it?"

**If you don't know:** "Good question. We haven't tested that yet. Here's how we'd approach it…" Never guess a number.

---

## Sources (if a judge asks)
- METR / Redwood Research investigation, Aug 26, 2026 — the 1,200 / 70,000 / 700 numbers and tool-call spoofing (~7% of transcripts).
- Hugging Face technical timeline, July 27, 2026 — "On their own, each was ambiguous"; ~17,600 attacker actions over ~4.5 days.
