import os
# Tests must never pick up a developer .env (and hit Atlas) by accident.
os.environ.setdefault("SWARMGUARD_SKIP_DOTENV", "1")

import pytest
from backend.app.store import MemoryStore

@pytest.fixture()
def store():
    return MemoryStore()
