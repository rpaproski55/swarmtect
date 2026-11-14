"""Idempotent Atlas setup: indexes + validators-lite. Run with MONGODB_URI set.
Fails loudly if Atlas is unreachable — never fakes success."""
import os, sys
sys.path.insert(0, ".")
from pymongo import MongoClient, ASCENDING

def main():
    from backend.app.store import load_env
    load_env()
    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        print("MONGODB_URI not set — Atlas setup NOT run. Set it in .env and re-run.")
        sys.exit(2)
    db = MongoClient(uri, serverSelectionTimeoutMS=8000)[os.environ.get("MONGODB_DB", "swarmguard")]
    db.command("ping")
    db["events"].create_index([("tenant_id", ASCENDING), ("ts", ASCENDING)])
    db["events"].create_index([("tenant_id", ASCENDING), ("agent_id", ASCENDING), ("ts", ASCENDING)])
    db["events"].create_index([("tenant_id", ASCENDING), ("resource_id", ASCENDING), ("ts", ASCENDING)])
    db["events"].create_index([("tenant_id", ASCENDING), ("artifact_id", ASCENDING), ("ts", ASCENDING)])
    # _id is unique by definition in MongoDB; an explicit unique _id index spec is rejected (found on real mongod).
    db["gateway_effects"].create_index([("tenant_id", ASCENDING), ("action_id", ASCENDING)], unique=True)
    db["episodes"].create_index([("tenant_id", ASCENDING), ("status", ASCENDING), ("detected_at", ASCENDING)])
    db["agents"].create_index([("tenant_id", ASCENDING), ("_id", ASCENDING)])
    ensure_vector_index(db)
    print("Atlas indexes created/verified (incl. Vector Search index 'verified_cases_vector').")

def ensure_vector_index(db):
    """Atlas Vector Search index with Automated Embeddings (Voyage) on verified_cases.case_text,
    pre-filtered by tenant_id + review_status. Idempotent."""
    from pymongo.operations import SearchIndexModel
    coll = db["verified_cases"]
    if "verified_cases" not in db.list_collection_names():
        db.create_collection("verified_cases")
    if any(ix.get("name") == "verified_cases_vector" for ix in coll.list_search_indexes()):
        return
    coll.create_search_index(SearchIndexModel(name="verified_cases_vector", type="vectorSearch", definition={
        "fields": [
            {"type": "autoEmbed", "path": "case_text", "model": "voyage-4", "modality": "text"},
            {"type": "filter", "path": "tenant_id"},
            {"type": "filter", "path": "review_status"},
        ]}))

if __name__ == "__main__":
    main()
