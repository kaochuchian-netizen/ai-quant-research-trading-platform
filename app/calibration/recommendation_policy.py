"""Advisory-only recommendation policy for calibration findings."""
from __future__ import annotations
from typing import Any
from .schemas import CalibrationFinding, CalibrationRecommendation
def _rec(idx: int, severity: str, area: str, finding: str, evidence: str, action: str, metrics: dict[str, Any], sample_size: int, limitations: list[str] | None = None) -> CalibrationRecommendation:
    return CalibrationRecommendation(f"calibration-rec-{idx:03d}", severity, area, finding, evidence, action, False, True, metrics, sample_size, limitations or [])
def build_calibration_findings(bucket_rows: list[dict[str, Any]], overall: dict[str, Any], rating_rows: list[dict[str, Any]], action_rows: list[dict[str, Any]], high_low: dict[str, Any], coverage_rows: list[dict[str, Any]]) -> list[CalibrationFinding]:
    findings: list[CalibrationFinding] = []
    for idx, row in enumerate(bucket_rows, 1):
        if row.get("finding") in {"over_confident", "under_confident", "well_calibrated", "unstable", "insufficient_sample"}:
            findings.append(CalibrationFinding(f"bucket-{idx:02d}", "confidence_formula", str(row.get("finding")), "medium" if row.get("finding") in {"over_confident", "under_confident"} else "info", f"Bucket {row.get('bucket')} gap={row.get('calibration_gap')}", int(row.get("sample_size") or 0), [] if int(row.get("sample_size") or 0) >= 20 else ["sample size below reliable threshold"] ))
    for area, rows in (("rating_rule", rating_rows), ("action_rule", action_rows), ("source_coverage_policy", coverage_rows)):
        for row in rows:
            if row.get("finding") in {"inverted", "weakly_effective", "coverage_policy_too_strict", "coverage_policy_too_loose"}:
                findings.append(CalibrationFinding(f"{area}-{len(findings)+1:02d}", area, str(row.get("finding")), "medium", f"{area} row={row}", int(row.get("sample_size") or 0), ["advisory-only diagnostic"]))
    if high_low.get("finding") not in {"well_calibrated_range", "not_available"}:
        findings.append(CalibrationFinding("high-low-01", "high_low_forecast", str(high_low.get("finding")), "medium", f"high/low finding {high_low.get('finding')}", int(high_low.get("sample_size") or 0), ["does not change formula"]))
    if not findings:
        findings.append(CalibrationFinding("calibration-available", "data_collection", str(overall.get("finding", "not_available")), "info", "No production logic change recommended from current sample.", int(overall.get("usable_sample_size") or 0), ["offline sample only"]))
    return findings
def build_recommendations(findings: list[CalibrationFinding]) -> list[CalibrationRecommendation]:
    recs: list[CalibrationRecommendation] = []
    for idx, f in enumerate(findings, 1):
        if f.finding == "over_confident": action = "Lower future confidence cap candidate for affected bucket after human review and larger backtest."
        elif f.finding == "under_confident": action = "Investigate conservative confidence formula candidate after human review and larger backtest."
        elif f.finding == "insufficient_sample": action = "Collect more prediction history before changing production weights or rules."
        elif f.target_area == "rating_rule": action = "Investigate rating A/B/C/D/E ordering offline; do not mutate rating rules."
        elif f.target_area == "action_rule": action = "Investigate action grouping offline; do not promote actions into trading signals."
        elif f.target_area == "source_coverage_policy": action = "Review confidence cap policy offline; keep current production policy unchanged."
        elif f.target_area == "high_low_forecast": action = "Research high/low bias offline; do not change forecast formula."
        else: action = "Retain advisory-only monitoring and collect more data."
        recs.append(_rec(idx, f.severity, f.target_area, f.finding, f.evidence_summary, action, {"finding_id": f.finding_id}, f.sample_size, f.limitations or ["offline deterministic analysis only"]))
    if not recs:
        recs.append(_rec(1, "info", "data_collection", "not_available", "No usable calibration findings.", "Collect deterministic prediction/evaluation history.", {}, 0, ["no usable samples"]))
    return recs
