# 3-minute judge demo

**0:00 — Pitch.** "A thousand agents can each look harmless while their collective behavior becomes dangerous. SwarmGuard watches their shared resources, connects the evidence, and prevents unauthorized actions before they execute."

**0:20 — Benign challenge (judge picks it).** Click *Run BENIGN collaboration*. 8 agents across Marketing + Support share `market_brief` under an approved collaboration. Result: 0 episodes, 0 quarantines. "Connectivity is not collusion — authorization decides."

**0:50 — Trigger the swarm.** Click *Trigger unauthorized shared board*. Real gateway traffic: a QA agent writes to unapproved `board_alpha`, Marketing/Procurement agents read it, then one attempts `request_sensitive_doc` on `sensitive_mock_dataset`.

**1:20 — Prevention proof.** The sensitive attempt is **denied before effect**: open the episode — `gateway_effects` shows `executed: false`, the resource ledger has zero entries for that resource. Not a warning after the fact; the effect never happened.

**1:50 — Episode evidence.** Episode detail shows rules R2 + R3 + R4 + R6, the write→read lineage, all evidence event IDs, the 5 affected agents across 3 tasks — and only those agents are quarantined. An unrelated agent still completes work live.

**2:20 — Baseline contrast.** Per-agent baseline on the same stream in S3 (fragmented) finds nothing — each action alone is weak. SwarmGuard connects them into one episode. Show `results/metrics.json`: 10/10 seeded detections, 0 false positives on benign runs.

**2:50 — Honest limits.** "This models one class of unauthorized shared-memory coordination at instrumented tool boundaries. It would not by itself have prevented the real Hugging Face incident — unseen network/filesystem channels need external telemetry. Atlas Vector Search case memory activates once the Atlas URI + embedding key are wired; until then it's a labelled fallback, and STATUS.md says so."
