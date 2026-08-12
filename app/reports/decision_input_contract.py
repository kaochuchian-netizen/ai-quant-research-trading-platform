"""Read-only Decision Layer declarations consumed by intelligence health.

These declarations describe input readiness only. They do not calculate or
change actions, eligibility, ranking, trade geometry, or execution.
"""
from __future__ import annotations

from typing import Any

TW_DECISION_INPUT_CONTRACT = {
    "contract_id": "tw_decision_input_health_contract_v1",
    "owner": "Decision Layer",
    "purpose": "readiness_health_only",
    "required_inputs": ["market_data", "technical_evidence", "research_evidence"],
    "action_policy_affected": False,
}


def tw_decision_required_inputs(
    *, symbol: str, market_data: bool, technical_evidence: bool,
    research_evidence: bool,
) -> dict[str, Any]:
    return {
        "symbol": str(symbol), "applicable": True,
        "contract": dict(TW_DECISION_INPUT_CONTRACT),
        "required_inputs": {
            "market_data": bool(market_data),
            "technical_evidence": bool(technical_evidence),
            "research_evidence": bool(research_evidence),
        },
    }
