"""Overall confidence calibration metrics."""
from __future__ import annotations
from .schemas import ConfidenceBucketResult, pct
def build_overall_calibration_metrics(buckets: list[ConfidenceBucketResult]) -> dict[str, object]:
    usable = [b for b in buckets if b.sample_size > 0 and b.direction_hit_rate is not None and b.avg_confidence is not None]
    total_usable = sum(b.sample_size for b in usable)
    unavailable = sum(b.unavailable_count for b in buckets)
    if total_usable == 0:
        return {"total_sample_size": unavailable, "usable_sample_size": 0, "unavailable_sample_size": unavailable, "weighted_expected_calibration_error": None, "mean_calibration_gap": None, "finding": "not_available", "over_confident_bucket_count": 0, "under_confident_bucket_count": 0, "well_calibrated_bucket_count": 0, "insufficient_bucket_count": sum(1 for b in buckets if b.finding == "insufficient_sample")}
    ece = sum((b.sample_size / total_usable) * abs(float(b.direction_hit_rate) - float(b.avg_confidence)) for b in usable)
    gaps = [float(b.calibration_gap) for b in usable if b.calibration_gap is not None]
    return {"total_sample_size": total_usable + unavailable, "usable_sample_size": total_usable, "unavailable_sample_size": unavailable, "weighted_expected_calibration_error": pct(ece), "mean_calibration_gap": pct(sum(gaps)/len(gaps)) if gaps else None, "finding": "usable" if total_usable >= 20 else "insufficient_sample", "over_confident_bucket_count": sum(1 for b in buckets if b.finding == "over_confident"), "under_confident_bucket_count": sum(1 for b in buckets if b.finding == "under_confident"), "well_calibrated_bucket_count": sum(1 for b in buckets if b.finding == "well_calibrated"), "insufficient_bucket_count": sum(1 for b in buckets if b.finding == "insufficient_sample")}
