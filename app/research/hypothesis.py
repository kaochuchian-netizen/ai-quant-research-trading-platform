"""Research hypotheses, explicitly separated from trade signals."""
from __future__ import annotations

from typing import Any


def build_hypothesis(reasoning: dict[str, Any], *, expected_trigger: str, invalidation: str) -> dict[str, Any]:
    if not expected_trigger.strip() or not invalidation.strip():
        raise ValueError("hypothesis requires trigger and invalidation")
    mapping = {"bullish": "bullish", "bearish": "bearish", "mixed": "uncertain", "insufficient_evidence": "uncertain"}
    return {
        "schema_version": "research_hypothesis_v1", "market": reasoning["market"], "symbol": reasoning["symbol"],
        "statement": f"若 {expected_trigger}，研究假設偏向 {mapping[reasoning['conclusion']]}",
        "expected_direction": mapping[reasoning["conclusion"]], "expected_trigger": expected_trigger,
        "invalidation": invalidation, "supporting_evidence_ids": reasoning["supporting_evidence_ids"],
        "opposing_evidence_ids": reasoning["opposing_evidence_ids"], "counter_argument": reasoning["counter_argument"],
        "research_hypothesis_only": True, "trade_signal": False, "trade_action": None,
        "review_hook": {"hypothesis_review": "pending", "evidence_review": "pending", "conflict_review": reasoning["conflict"]["level"], "missing_evidence_review": reasoning["missing_evidence"]},
    }


def validate_hypothesis(value: dict[str, Any]) -> list[str]:
    errors = []
    if not value.get("expected_trigger"): errors.append("trigger_missing")
    if not value.get("invalidation"): errors.append("invalidation_missing")
    if value.get("research_hypothesis_only") is not True or value.get("trade_signal") is not False or value.get("trade_action") is not None: errors.append("hypothesis_trade_boundary")
    return errors
