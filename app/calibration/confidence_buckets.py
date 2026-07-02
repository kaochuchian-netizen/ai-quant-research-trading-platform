"""Confidence bucket calibration analysis."""
from __future__ import annotations
from .schemas import CalibrationSample, ConfidenceBucketResult, mean, pct
DEFAULT_BUCKETS = [(0.40,0.50),(0.50,0.60),(0.60,0.70),(0.70,0.80),(0.80,0.90),(0.90,1.0000001)]
def bucket_label(lo: float, hi: float) -> str: return f"{lo:.2f}-{1.00 if hi > 1 else hi:.2f}"
def _finding(sample_size: int, gap: float | None) -> str:
    if sample_size < 5: return "insufficient_sample"
    if gap is None: return "not_available"
    if sample_size < 20: return "unstable"
    if gap <= -0.10: return "over_confident"
    if gap >= 0.10: return "under_confident"
    if abs(gap) <= 0.05: return "well_calibrated"
    return "unstable"
def _recommendation(finding: str, label: str) -> str:
    return {"over_confident": f"Review future confidence cap for bucket {label}; advisory only.", "under_confident": f"Investigate whether confidence is too conservative for bucket {label}; advisory only.", "well_calibrated": f"Keep collecting samples for bucket {label}; no production change.", "unstable": f"Collect more samples before changing bucket {label} behavior.", "insufficient_sample": f"Insufficient samples in bucket {label}; do not infer calibration.", "not_available": f"Direction hit unavailable in bucket {label}."}.get(finding, "No recommendation")
def analyze_confidence_buckets(samples: list[CalibrationSample], buckets: list[tuple[float,float]] | None = None) -> list[ConfidenceBucketResult]:
    results: list[ConfidenceBucketResult] = []
    for lo, hi in (buckets or DEFAULT_BUCKETS):
        selected = [s for s in samples if s.confidence is not None and lo <= s.confidence < hi]
        usable = [s for s in selected if s.direction_hit is not None]
        close = [s for s in selected if s.close_direction_hit is not None]
        avg_conf = mean([s.confidence for s in usable if s.confidence is not None])
        hit_rate = mean([1.0 if s.direction_hit else 0.0 for s in usable])
        close_rate = mean([1.0 if s.close_direction_hit else 0.0 for s in close])
        gap = None if avg_conf is None or hit_rate is None else hit_rate - avg_conf
        finding = _finding(len(usable), gap)
        label = bucket_label(lo, hi)
        results.append(ConfidenceBucketResult(label, len(usable), len(selected)-len(usable), pct(avg_conf), pct(hit_rate), pct(close_rate), pct(gap), pct(abs(gap)) if gap is not None else None, finding, _recommendation(finding, label)))
    return results
