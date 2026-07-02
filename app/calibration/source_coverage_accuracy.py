"""Source coverage readiness versus accuracy analysis."""
from __future__ import annotations
from .schemas import CalibrationSample, SourceCoverageAccuracyResult, READINESS_GROUPS, mean, pct
def analyze_source_coverage_accuracy(samples: list[CalibrationSample]) -> list[SourceCoverageAccuracyResult]:
    rows: list[SourceCoverageAccuracyResult] = []; avgs: dict[str,float|None] = {}
    for readiness in READINESS_GROUPS:
        group = [s for s in samples if s.source_coverage_readiness == readiness]
        hits = [1.0 if s.direction_hit else 0.0 for s in group if s.direction_hit is not None]
        conf = [s.confidence for s in group if s.confidence is not None]
        hit_rate = mean(hits); avg_conf = mean(conf); gap = None if hit_rate is None or avg_conf is None else hit_rate - avg_conf
        r1 = [s.actual_return_1d for s in group if s.actual_return_1d is not None]; r5 = [s.actual_return_5d for s in group if s.actual_return_5d is not None]; r20 = [s.actual_return_20d for s in group if s.actual_return_20d is not None]
        avgs[readiness] = hit_rate
        finding = "not_available" if not group else "insufficient_sample" if len(hits) < 5 else "coverage_policy_supported"
        rows.append(SourceCoverageAccuracyResult(readiness, len(hits), pct(hit_rate), pct(avg_conf), pct(gap), pct(mean(r1)), pct(mean(r5)), pct(mean(r20)), pct(mean([s.high_error_pct for s in group if s.high_error_pct is not None])), pct(mean([s.low_error_pct for s in group if s.low_error_pct is not None])), finding))
    ready = avgs.get("ready"); partial = avgs.get("partial"); insufficient = avgs.get("insufficient")
    adjusted = []
    for row in rows:
        finding = row.finding
        if row.sample_size >= 5:
            if ready is not None and partial is not None and partial > ready + 0.05: finding = "coverage_policy_too_strict" if row.source_coverage_readiness == "partial" else finding
            elif ready is not None and insufficient is not None and insufficient >= ready: finding = "insufficient_sample"
            elif row.source_coverage_readiness == "insufficient" and row.direction_hit_rate is not None and ready is not None and row.direction_hit_rate < ready: finding = "coverage_policy_supported"
            else: finding = "coverage_policy_supported"
        adjusted.append(SourceCoverageAccuracyResult(row.source_coverage_readiness, row.sample_size, row.direction_hit_rate, row.avg_confidence, row.calibration_gap, row.avg_return_1d, row.avg_return_5d, row.avg_return_20d, row.high_error_pct, row.low_error_pct, finding))
    return adjusted
