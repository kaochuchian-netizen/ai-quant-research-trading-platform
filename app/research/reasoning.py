"""Traceable research reasoning over normalized evidence and long-lived knowledge."""
from __future__ import annotations

from typing import Any

REQUIRED_CLASSES = ("market", "technical", "fundamental", "news", "sector")


def build_reasoning(market: str, symbol: str, evidence: list[dict[str, Any]], knowledge: dict[str, Any]) -> dict[str, Any]:
    counted = [x for x in evidence if x.get("counted_in_reasoning") and x["symbol_or_scope"] in {symbol.upper(), "MARKET"}]
    usable = [x for x in counted if x.get("coverage_status") == "AVAILABLE"]
    substantive = [x for x in usable if x.get("research_role", "substantive") == "substantive"]
    contextual = [x for x in usable if x.get("research_role") == "contextual"]
    supporting = [x for x in substantive if x["direction"] == "bullish"]
    opposing = [x for x in substantive if x["direction"] == "bearish"]
    neutral = [x for x in counted if x not in supporting and x not in opposing]
    present = {x["evidence_class"] for x in counted if x["coverage_status"] == "AVAILABLE"}
    missing = [name for name in REQUIRED_CLASSES if name not in present]
    if supporting and opposing: conclusion, conflict = "mixed", "HIGH" if any(x["materiality"] in {"high", "critical"} for x in supporting + opposing) else "MEDIUM"
    elif supporting: conclusion, conflict = "bullish", "LOW"
    elif opposing: conclusion, conflict = "bearish", "LOW"
    else: conclusion, conflict = "insufficient_evidence", "LOW"
    chains = []
    for item in counted:
        links = knowledge.get("dimensions", {}).get("long_term_drivers", []) + knowledge.get("dimensions", {}).get("macro_sensitivity", [])
        chains.append({
            "evidence_id": item["evidence_id"], "evidence_class": item["evidence_class"],
            "interpretation": f"{item['evidence_class']} evidence is {item['direction']}",
            "knowledge_context": links[:2], "decision_impact": item["direction"],
        })
    coverage_score = round(len(present) / len(REQUIRED_CLASSES) * 100, 2)
    evidence_quality = round(sum(x["reliability"] * x["confidence"] for x in counted) / max(1, len(counted)) * 100, 2)
    fresh_score = round(sum(x["coverage_status"] == "AVAILABLE" for x in counted) / max(1, len(counted)) * 100, 2)
    knowledge_score = 100 if knowledge.get("status") == "AVAILABLE" else 40
    conflict_score = 35 if conflict == "HIGH" else 65 if conflict == "MEDIUM" else 100
    score = round(evidence_quality * .35 + coverage_score * .25 + knowledge_score * .15 + conflict_score * .15 + fresh_score * .10, 2)
    caps = []
    if missing: caps.append("MISSING_EVIDENCE_CLASSES")
    if conflict != "LOW": caps.append("CONFLICTING_EVIDENCE")
    if knowledge.get("status") != "AVAILABLE": caps.append("KNOWLEDGE_PARTIAL")
    return {
        "schema_version": "research_reasoning_v1", "market": market.upper(), "symbol": symbol.upper(),
        "conclusion": conclusion, "why": [x["summary"] for x in supporting[:3]] or [x["summary"] for x in opposing[:3]],
        "why_not": [x["summary"] for x in opposing[:3]] if conclusion == "bullish" else [x["summary"] for x in supporting[:3]],
        "supporting_evidence_ids": [x["evidence_id"] for x in supporting],
        "opposing_evidence_ids": [x["evidence_id"] for x in opposing],
        "neutral_evidence_ids": [x["evidence_id"] for x in neutral],
        "contextual_evidence_ids": [x["evidence_id"] for x in contextual],
        "substantive_evidence_ids": [x["evidence_id"] for x in substantive],
        "missing_evidence": missing, "reasoning_chain": chains,
        "conflict": {"level": conflict, "method": "explicit_directional_conflict_no_averaging"},
        "confidence": {"score": score, "components": {"evidence": evidence_quality, "coverage": coverage_score, "knowledge": knowledge_score, "conflict": conflict_score, "freshness": fresh_score}, "cap_reasons": caps},
        "counter_argument": (opposing[0]["summary"] if opposing else supporting[0]["summary"] if supporting else "可用證據不足，任何方向性結論都可能失效"),
        "unknowns": missing, "research_only": True, "trade_action": None,
    }


def validate_reasoning(value: dict[str, Any], evidence_ids: set[str]) -> list[str]:
    errors = []
    cited = set(value.get("supporting_evidence_ids", [])) | set(value.get("opposing_evidence_ids", [])) | set(value.get("neutral_evidence_ids", []))
    if not cited <= evidence_ids: errors.append("untraceable_evidence")
    if value.get("conclusion") != "insufficient_evidence" and not cited: errors.append("conclusion_without_evidence")
    if not isinstance(value.get("supporting_evidence_ids"), list) or not isinstance(value.get("opposing_evidence_ids"), list): errors.append("bidirectional_evidence_missing")
    if any(step.get("evidence_id") not in evidence_ids for step in value.get("reasoning_chain", [])): errors.append("reasoning_chain_untraceable")
    if not value.get("counter_argument"): errors.append("counter_argument_missing")
    if value.get("research_only") is not True or value.get("trade_action") is not None: errors.append("research_decision_boundary")
    return errors
