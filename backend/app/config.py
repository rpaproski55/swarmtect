"""Single source of truth for detection rules: configs/rules.yaml (loaded once)."""
from __future__ import annotations
import pathlib
from functools import lru_cache

RULES_PATH = pathlib.Path(__file__).resolve().parents[2] / "configs" / "rules.yaml"

DEFAULTS = {
    "window_seconds": 180, "alert_threshold": 40,
    "weights": {"R1_POLICY_BREACH": 30, "R2_UNAUTHORIZED_BRIDGE": 25, "R3_PROPAGATION": 35,
                "R4_GOAL_DRIFT": 25, "R5_TELEMETRY_MISMATCH": 20, "R6_HIGH_IMPACT": 30},
    "high_impact_tools": ["request_sensitive_doc", "export_data", "grant_access"],
    "propagation_min_agents": 3, "propagation_min_tasks": 2,
}


@lru_cache(maxsize=1)
def load_rules() -> dict:
    import yaml
    data = yaml.safe_load(RULES_PATH.read_text()) if RULES_PATH.exists() else {}
    return {**DEFAULTS, **(data or {})}


def rules(overrides: dict | None = None) -> dict:
    return {**load_rules(), **(overrides or {})}
