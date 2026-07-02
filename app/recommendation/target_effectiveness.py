"""Prediction target effectiveness summaries."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, Iterable, List
from .schemas import bool_rate, safe_avg, usable_samples

def compute_target_effectiveness(samples: Iterable[Dict[str, Any]], factor_effectiveness: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    factors_by_name = {row["factor_group"]: row for row in factor_effectiveness}
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in samples:
        grouped[row.get("prediction_target", "unknown")].append(row)
    output = []
    for target, rows in sorted(grouped.items()):
        base = usable_samples(rows) or rows
        ranked = sorted({row.get("factor_group") for row in rows}, key=lambda key: factors_by_name.get(key, {}).get("effectiveness_score", 0), reverse=True)
        output.append({
            "prediction_target": target,
            "sample_size": len(rows),
            "hit_rate": bool_rate(row.get("is_hit") for row in base),
            "interval_coverage": bool_rate(row.get("interval_covered") for row in base),
            "avg_evidence_score": safe_avg(row.get("evidence_score", 0) for row in base),
            "top_factor_groups": ranked[:3],
            "weak_or_inverted_factor_groups": [key for key in ranked if factors_by_name.get(key, {}).get("finding") in {"weakly_effective", "inverted", "noisy", "insufficient_sample"}],
            "source_coverage_dependency": sorted({row.get("source_priority") for row in rows}),
            "production_mutation_allowed": False,
        })
    return output
