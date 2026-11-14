# Architecture

LangGraph / simulated agents → **Trusted Gateway** (pre-action policy + quarantine check, effect receipt) → **Store** (MongoDB Atlas when `MONGODB_URI` set; in-memory fallback with identical interface, always labelled) → **Detector** (sliding evidence graph, rules R1–R6 in `configs/rules.yaml` weights) → **Episodes + containment** (quarantine only on policy breach + corroborating evidence, or operator action) → **FastAPI + cockpit** (counters recomputed from stored records).

Trust tiers: gateway/resource-ledger events are `authoritative`; agent self-reports are `self_reported` and can only *lose* an argument against the ledger (R5), never win one.

Truth hygiene: simulator truth lives only in scenario return values for post-hoc metrics. It is stripped from event metadata in `Gateway._event`, and a test asserts no event carries a truth label.

Vector index `verified_cases_vector` (created by `scripts/setup_atlas.py`): Atlas Automated Embeddings (`autoEmbed`, Voyage `voyage-4`) on `verified_cases.case_text`, filter fields `tenant_id` and `review_status`. Atlas embeds case text at index time and the query text at query time, so the app has no embedding pipeline. `backend/app/memory.py` pre-filters on tenant: no cross-tenant retrieval (verified on the sandbox cluster: a paraphrased query matched the `demo` case at score 0.81 and never returned the `tenant2` case).

Change Streams / SSE: not used for blocking (stream latency can't guarantee prevention). Dashboard polls; that is labelled in the UI path, per brief §4.
