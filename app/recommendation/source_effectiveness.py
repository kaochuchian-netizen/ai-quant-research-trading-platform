"""Source effectiveness analysis with priority and availability guardrails."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Tuple
from .schemas import bool_rate, safe_avg, usable_samples

def compute_source_effectiveness(samples: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in samples:
        groups[(row.get("source_priority", "unknown"), row.get("source_category", "unknown"), row.get("source_id", "unknown"))].append(row)
    output = []
    for (priority, category, source_id), rows in sorted(groups.items()):
        usable = usable_samples(rows)
        base = usable or rows
        noisy = priority == "D_sentiment_or_noise"
        aggregated = priority == "C_market_aggregated"
        output.append({
            "source_priority": priority,
            "source_category": category,
            "source_id": source_id,
            "sample_size": len(rows),
            "usable_sample_size": len(usable),
            "source_available_rate": bool_rate(row.get("source_available") for row in rows),
            "source_ready_rate": bool_rate(row.get("source_ready") for row in rows),
            "hit_rate": bool_rate(row.get("is_hit") for row in base),
            "avg_evidence_score": safe_avg(row.get("evidence_score", 0) for row in base),
            "avg_contribution_score": safe_avg(row.get("contribution_score", 0) for row in base),
            "priority_change_allowed": False,
            "recommended_use": "supporting_sentiment_only" if noisy else "market_context_only" if aggregated else "candidate_primary_or_secondary_evidence",
            "limitations": sorted({row.get("limitation") for row in rows if row.get("limitation")}) or ["read-only dry-run sample"],
        })
    return output
