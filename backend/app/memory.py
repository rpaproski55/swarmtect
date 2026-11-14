"""Verified-case memory. Uses Atlas $vectorSearch ONLY when a Mongo backend,
an embedding, and a vector index are actually present. Otherwise a clearly
labelled lexical fallback — never misrepresented as Vector Search."""
from __future__ import annotations
from .models import new_id, now

def store_verified_case(store, tenant_id, case_text, episode_id, evidence_event_ids, embedding=None, model=None):
    if embedding is None:
        embedding = embed_local(case_text)  # local fallback embedding; real deployments use Voyage via Atlas
        model = model or "local-hash-64 (fallback, not Voyage)"
    return store.insert("verified_cases", {
        "_id": new_id("case"), "tenant_id": tenant_id, "case_text": case_text, "label": "coordination_episode",
        "provenance_episode_id": episode_id, "evidence_event_ids": evidence_event_ids,
        "validation": "operator_confirmed", "review_status": "verified",
        "embedding": embedding, "embedding_model": model, "created_at": now().isoformat(), "expires_at": None})

def confirm_episode_as_case(store, tenant_id, episode_id):
    ep = store.find_one("episodes", {"_id": episode_id, "tenant_id": tenant_id})
    if not ep:
        return None
    existing = store.find_one("verified_cases", {"provenance_episode_id": episode_id, "tenant_id": tenant_id})
    if existing:
        return existing
    case_text = (f"coordination episode rules {' '.join(ep['triggered_rules'])} tasks {' '.join(ep['task_ids'])} "
                 f"artifacts {' '.join(ep['artifact_ids'])} unauthorized board propagation high impact denied")
    return store_verified_case(store, tenant_id, case_text, episode_id, ep["evidence_event_ids"])

VECTOR_INDEX = "verified_cases_vector"   # Atlas Vector Search index, autoEmbed on case_text (voyage-4)
AUTO_EMBED_MODEL = "voyage-4"

def search_cases(store, tenant_id, query_text, embedding=None, limit=3):
    """Atlas Vector Search over verified cases, tenant pre-filtered.

    The index uses Atlas Automated Embeddings: Atlas embeds `case_text` with
    Voyage at index time and embeds `query_text` at query time, so the app ships
    no embedding pipeline. Falls back to a clearly labelled lexical search when
    not on Atlas or when the vector query fails."""
    if getattr(store, "backend", "") == "mongodb-atlas":
        try:
            pipeline = [
                {"$vectorSearch": {"index": VECTOR_INDEX, "path": "case_text",
                                   "query": {"text": query_text}, "numCandidates": 50, "limit": limit,
                                   "filter": {"tenant_id": tenant_id, "review_status": "verified"}}},
                {"$project": {"_id": 1, "case_text": 1, "provenance_episode_id": 1,
                              "evidence_event_ids": 1, "score": {"$meta": "vectorSearchScore"}}},
            ]
            return {"mode": f"atlas_vector_search_auto_embed_{AUTO_EMBED_MODEL}",
                    "results": list(store.db["verified_cases"].aggregate(pipeline))}
        except Exception as e:
            return {"mode": "lexical_fallback_after_vector_error", "error": str(e), "results": _lexical(store, tenant_id, query_text, limit)}
    return {"mode": "lexical_fallback_no_vector_index_or_embedding", "results": _lexical(store, tenant_id, query_text, limit)}

def embed_local(text: str, dim: int = 64) -> list[float]:
    """Deterministic hashing embedding for LOCAL fallback ranking only.
    Labelled as such wherever used — it is not Voyage/Atlas Vector Search."""
    import hashlib, math
    vec = [0.0] * dim
    for w in text.lower().split():
        h = int(hashlib.sha256(w.encode()).hexdigest()[:8], 16)
        vec[h % dim] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))

def search_cases_local_embedding(store, tenant_id, query_text, limit=3):
    q = embed_local(query_text)
    scored = []
    for c in store.find("verified_cases", {"tenant_id": tenant_id, "review_status": "verified"}):
        emb = c.get("embedding") or embed_local(c["case_text"])
        scored.append((cosine(q, emb), c))
    scored.sort(key=lambda x: -x[0])
    return {"mode": "local_hash_embedding_fallback_NOT_atlas_vector_search",
            "results": [{"_id": c["_id"], "case_text": c["case_text"], "score": round(s, 4),
                         "provenance_episode_id": c["provenance_episode_id"],
                         "evidence_event_ids": c["evidence_event_ids"]} for s, c in scored[:limit] if s > 0.05]}

def _lexical(store, tenant_id, query_text, limit):
    words = {w.lower() for w in query_text.split() if len(w) > 3}
    scored = []
    for c in store.find("verified_cases", {"tenant_id": tenant_id, "review_status": "verified"}):
        text_words = {w.lower().strip(".,") for w in c["case_text"].split()}
        scored.append((len(words & text_words), c))
    scored.sort(key=lambda x: -x[0])
    return [{"_id": c["_id"], "case_text": c["case_text"], "provenance_episode_id": c["provenance_episode_id"],
             "evidence_event_ids": c["evidence_event_ids"], "lexical_overlap": s} for s, c in scored[:limit] if s > 0]
