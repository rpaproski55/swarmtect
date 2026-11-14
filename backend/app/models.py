from __future__ import annotations
import hashlib, uuid
from datetime import datetime, timezone

def now() -> datetime:
    return datetime.now(timezone.utc)

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"

def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]
