# 3-minute judge demo

**0:00 — Pitch.** "A thousand agents can each look harmless while their collective behavior becomes dangerous. SwarmGuard watches their shared resources, connects the evidence, and prevents unauthorized actions before they execute."

**0:20 — Benign challenge (judge picks it).** Open `/` and click **Step 1 · Approved teamwork** (or press `→`). The swarm map draws the real events in order: 8 agents across Marketing + Support share `market_brief` under an approved collaboration. Result: 0 episodes, 0 quarantines. "Connectivity is not collusion — authorization decides."

**0:50 — Trigger the swarm.** Click **Step 2 · Unapproved swarm**. The map replays the real gateway events: Real gateway traffic: a QA agent writes to unapproved `board_alpha`, Marketing/Procurement agents read it, then one attempts `request_sensitive_doc` on `sensitive_mock_dataset`.

**1:20 — Prevention proof.** The sensitive attempt is **denied before effect**: the map ends on a red BLOCKED node; open *Show technical evidence* — the gateway table shows `executed: false`, the resource ledger has zero entries for that resource. Not a warning after the fact; the effect never happened.

**1:50 — Episode evidence.** Episode detail shows rules R2 + R3 + R4 + R6, the write→read lineage, all evidence event IDs, the 5 affected agents across 3 tasks — and only those agents are quarantined. An unrelated agent still completes work live.

**2:05 — Memory.** Click **Step 3 · Remember it**: the episode is confirmed as a verified case, the swarm happens again, and the new incident is matched to that case via Atlas Vector Search (Voyage auto-embeddings). Advisory only; the gateway still does the blocking. *(Optional: **Bonus · Real LangGraph agents** shows the same detection on 4 live LangGraph agents.)*

**2:20 — Baseline contrast.** Per-agent baseline on the same stream in S3 (fragmented) finds nothing — each action alone is weak. SwarmGuard connects them into one episode. Say it plainly: these are 6 deterministic scenarios, each passing; S1 and S0 (benign) raise nothing.

**2:50 — Honest limits.** "This models one class of unauthorized shared-memory coordination at instrumented tool boundaries. It would not by itself have prevented the real Hugging Face incident — unseen network/filesystem channels need external telemetry. Case memory runs on Atlas Vector Search with Automated Embeddings (verified on our sandbox cluster); without Atlas it shows a labelled fallback."
