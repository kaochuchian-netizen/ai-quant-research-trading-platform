"""Forecast horizon effectiveness summaries."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Tuple
from .schemas import bool_rate, safe_avg, usable_samples

def compute_horizon_effectiveness(samples: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in samples:
        groups[(row.get("horizon", "unknown"), row.get("factor_group", "unknown"))].append(row)
    output = []
    for (horizon, factor_group), rows in sorted(groups.items()):
        base = usable_samples(rows) or rows
        output.append({
            "horizon": horizon,
            "factor_group": factor_group,
            "sample_size": len(rows),
            "hit_rate": bool_rate(row.get("is_hit") for row in base),
            "interval_coverage": bool_rate(row.get("interval_covered") for row in base),
            "avg_error_pct": safe_avg(abs(row.get("actual_return_pct", 0) - row.get("predicted_return_pct", 0)) for row in base),
            "avg_contribution_score": safe_avg(row.get("contribution_score", 0) for row in base),
            "production_mutation_allowed": False,
        })
    return output
