"""Factor effectiveness scoring for read-only dry-run artifacts."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Dict, Iterable, List
from .schemas import bool_rate, positive_rate, safe_avg, safe_median, usable_samples

def _finding(sample_size: int, hit: float, avg_return: float, contribution: float, gap: float) -> str:
    if sample_size < 5:
        return "insufficient_sample"
    if hit >= 0.62 and avg_return > 0 and contribution >= 0.45 and gap <= 0.18:
        return "effective"
    if hit >= 0.53 and avg_return >= -0.1 and contribution >= 0.30:
        return "weakly_effective"
    if hit <= 0.42 and avg_return < 0:
        return "inverted"
    return "noisy"

def compute_factor_effectiveness(samples: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in samples:
        groups[str(row.get("factor_group", "unknown"))].append(row)
    output = []
    for group, rows in sorted(groups.items()):
        usable = usable_samples(rows)
        base = usable or rows
        hit = bool_rate(row.get("is_hit") for row in base)
        avg_return = safe_avg(row.get("actual_return_pct", 0) for row in base)
        avg_contribution = safe_avg(row.get("contribution_score", 0) for row in base)
        avg_conf = safe_avg(row.get("confidence", 0) for row in base)
        gap = abs(avg_conf - hit)
        score = round((hit * 0.35 + positive_rate(row.get("actual_return_pct", 0) for row in base) * 0.20 + avg_contribution * 0.25 + max(0, 1 - gap) * 0.20) * 100, 3)
        output.append({
            "factor_group": group,
            "sample_size": len(rows),
            "usable_sample_size": len(usable),
            "hit_rate": hit,
            "interval_coverage": bool_rate(row.get("interval_covered") for row in base),
            "avg_actual_return_pct": avg_return,
            "median_actual_return_pct": safe_median(row.get("actual_return_pct", 0) for row in base),
            "positive_return_rate": positive_rate(row.get("actual_return_pct", 0) for row in base),
            "avg_contribution_score": avg_contribution,
            "avg_evidence_score": safe_avg(row.get("evidence_score", 0) for row in base),
            "confidence_calibration_gap": round(gap, 6),
            "effectiveness_score": score,
            "finding": _finding(len(usable), hit, avg_return, avg_contribution, gap),
            "production_mutation_allowed": False,
            "limitations": sorted({row.get("limitation") for row in rows if row.get("limitation")}) or ["offline dry-run only"],
        })
    return output
