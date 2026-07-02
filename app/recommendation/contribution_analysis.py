"""Factor contribution analysis with missing attribution handling."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, Iterable, List
from .schemas import bool_rate, safe_avg

def compute_contribution_analysis(samples: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in samples:
        grouped[row.get("factor_group", "unknown")].append(row)
    output = []
    for factor_group, rows in sorted(grouped.items()):
        missing = [row for row in rows if row.get("data_completeness", 0) < 0.7 or not row.get("source_available")]
        output.append({
            "factor_group": factor_group,
            "sample_size": len(rows),
            "attribution_missing_count": len(missing),
            "contribution_hit_rate": bool_rate(row.get("is_hit") for row in rows if row.get("contribution_score", 0) >= 0.25),
            "avg_contribution_score": safe_avg(row.get("contribution_score", 0) for row in rows),
            "missing_attribution_policy": "exclude from weight increase and keep for monitoring" if missing else "usable for dry-run comparison only",
            "production_mutation_allowed": False,
        })
    return output
