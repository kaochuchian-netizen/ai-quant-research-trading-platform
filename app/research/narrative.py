"""Deterministic market narrative synthesized from reasoning, not headlines."""
from __future__ import annotations

from collections import Counter
from typing import Any


def build_market_narrative(market: str, reasoning: list[dict[str, Any]]) -> dict[str, Any]:
    conclusions = Counter(x["conclusion"] for x in reasoning)
    conflicts = Counter(x["conflict"]["level"] for x in reasoning)
    missing = Counter(item for row in reasoning for item in row["missing_evidence"])
    lead = conclusions.most_common(1)[0][0] if conclusions else "insufficient_evidence"
    text = {
        "bullish": "研究證據整體偏多，但仍須檢查反向證據與失效條件。",
        "bearish": "研究證據整體偏空，主要風險尚未解除。",
        "mixed": "市場主線分歧，正反證據並存，暫不以單一敘事取代衝突。",
        "insufficient_evidence": "研究覆蓋不足，現階段以已知證據與缺口並列呈現。",
    }[lead]
    return {"schema_version": "research_market_narrative_v1", "market": market.upper(), "narrative": text,
            "dominant_research_state": lead, "conclusion_distribution": dict(conclusions),
            "conflict_distribution": dict(conflicts), "largest_unknowns": [x for x, _ in missing.most_common(3)],
            "method": "cross_symbol_reasoning_synthesis_not_headline_concatenation"}
