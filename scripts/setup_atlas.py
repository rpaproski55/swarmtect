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
    print("Atlas indexes created/verified. Vector index for verified_cases.embedding must be created")
    print("in Atlas UI/Search with filter fields tenant_id + review_status (see docs/ARCHITECTURE.md).")

if __name__ == "__main__":
    main()
