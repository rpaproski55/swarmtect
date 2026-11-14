"""Agent credentials for the HTTP gateway routes.

Each agent gets a key = HMAC-SHA256(AGENT_KEY_SECRET, "tenant:agent"). An HTTP caller
must present the key for the agent it claims to be (header x-agent-key), so nobody on
the network can act as (or frame) another agent. In-process runtimes (simulator,
LangGraph S6, Agent Engine tool) call Gateway directly and are the trusted runtime.
Static HMAC keys are a hackathon-grade stand-in for workload identity (mTLS / SPIFFE).
"""
from __future__ import annotations
import hashlib, hmac, logging, os

DEV_DEFAULT = "dev-agent-key-secret"
_warned = False


def _secret() -> bytes:
    global _warned
    s = os.environ.get("AGENT_KEY_SECRET", DEV_DEFAULT)
    if s == DEV_DEFAULT and not _warned:
        logging.getLogger("swarmguard").warning("AGENT_KEY_SECRET not set: using the dev default (demo only)")
        _warned = True
    return s.encode()


def issue_agent_key(tenant_id: str, agent_id: str) -> str:
    return hmac.new(_secret(), f"{tenant_id}:{agent_id}".encode(), hashlib.sha256).hexdigest()


def verify_agent_key(tenant_id: str, agent_id: str, key: str | None) -> bool:
    return bool(key) and hmac.compare_digest(issue_agent_key(tenant_id, agent_id), key)
