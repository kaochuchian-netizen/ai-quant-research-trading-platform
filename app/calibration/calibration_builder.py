"""Build deterministic AI-DEV-124 confidence calibration artifacts."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from .action_effectiveness import analyze_action_effectiveness
from .calibration_metrics import build_overall_calibration_metrics
from .confidence_buckets import analyze_confidence_buckets
from .high_low_error import analyze_high_low_error
from .rating_effectiveness import analyze_rating_effectiveness
from .recommendation_policy import build_calibration_findings, build_recommendations
from .schemas import ConfidenceCalibrationArtifact, INPUT_SCHEMA_VERSION, SCHEMA_VERSION, CalibrationInput, CalibrationSample, input_from_dict
from .source_coverage_accuracy import analyze_source_coverage_accuracy
FORBIDDEN_FALSE = {"broker_login": False, "simulation_order": False, "production_order": False, "line_send": False, "email_send": False, "scheduler_change": False, "production_db_write": False, "secrets_read": False, "production_forecast_weight_change": False, "production_confidence_mutation": False, "production_rating_action_rule_mutation": False, "large_ai_or_gemini_batch_call": False, "dashboard_production_publish": False, "nginx_systemd_cron_mutation": False, "trading_execution_run": False}
def _sample(i:int, conf:float, hit:bool|None, rating:str, action:str, readiness:str, r:float, pred:bool=True) -> CalibrationSample:
    base_high = 100 + (i % 7); base_low = 95 - (i % 3); actual_high = base_high * (1.01 if i % 4 == 0 else 0.99); actual_low = base_low * (0.99 if i % 5 == 0 else 1.01)
    return CalibrationSample(SCHEMA_VERSION, f"cal-v1-{i:03d}", "2330" if i % 2 else "2317", "sample-stock", "next_day_high_low" if pred else "rating_action", "2026-01-02", f"2026-01-{3 + (i % 20):02d}", conf, "ready" if readiness == "ready" else "capped", rating, conf*100, action, readiness, {"ready":0.9,"partial":0.65,"insufficient":0.35}.get(readiness,0.0), base_high if pred else None, base_low if pred else None, "up" if r >= 0 else "down", actual_high if pred else None, actual_low if pred else None, 100*(1+r), r, r*1.8, r*3.2, hit, hit if hit is not None else None, None, None, "evaluated" if hit is not None else "pending_actual_outcome", ["historical_csv_fallback", "twse_monthly_revenue"], [f"evidence-{i:03d}"], True)
def build_offline_sample_input() -> CalibrationInput:
    samples: list[CalibrationSample] = []
    # over-confident 0.70-0.80: 20 samples, 10 hits, avg confidence 0.75 -> gap -0.25
    for i in range(1, 21): samples.append(_sample(i, 0.75, i <= 10, ["A","B","C","D","E"][i%5], ["偏多加碼","偏多續抱","中性觀察","降低追價","保守觀望"][i%5], ["ready","partial","insufficient"][i%3], 0.02 if i <= 10 else -0.02))
    # under-confident 0.50-0.60: 20 samples, 14 hits, avg confidence 0.55 -> gap +0.15
    for j in range(21, 41): samples.append(_sample(j, 0.55, j <= 34, ["A","B","C","D","E"][j%5], ["偏多加碼","偏多續抱","中性觀察","降低追價","保守觀望"][j%5], ["ready","partial","insufficient"][j%3], 0.018 if j <= 34 else -0.018))
    # well calibrated 0.60-0.70: 20 samples, 13 hits, avg confidence 0.65 -> gap 0
    for j in range(41, 61): samples.append(_sample(j, 0.65, j <= 53, ["A","B","C","D","E"][j%5], ["偏多加碼","偏多續抱","中性觀察","降低追價","保守觀望"][j%5], ["ready","partial","insufficient"][j%3], 0.015 if j <= 53 else -0.015))
    # insufficient sample and missing high/low/not available case.
    for j in range(61, 65): samples.append(_sample(j, 0.85, j % 2 == 0, "unknown", "unknown", "unknown", 0.0, pred=False))
    samples.append(_sample(65, 0.45, None, "C", "中性觀察", "partial", 0.0, pred=False))
    return CalibrationInput(INPUT_SCHEMA_VERSION, samples, {"source": "deterministic_offline_sample", "ai_dev": "AI-DEV-124", "uses_real_history": False}, True)
def build_confidence_calibration_artifact(calibration_input: CalibrationInput | None = None) -> ConfidenceCalibrationArtifact:
    calibration_input = calibration_input or build_offline_sample_input(); samples = calibration_input.samples
    buckets = analyze_confidence_buckets(samples); bucket_rows = [b.to_dict() for b in buckets]
    overall = build_overall_calibration_metrics(buckets)
    rating_rows = [r.to_dict() for r in analyze_rating_effectiveness(samples)]
    action_rows = [r.to_dict() for r in analyze_action_effectiveness(samples)]
    high_low = analyze_high_low_error(samples).to_dict()
    coverage_rows = [r.to_dict() for r in analyze_source_coverage_accuracy(samples)]
    findings = build_calibration_findings(bucket_rows, overall, rating_rows, action_rows, high_low, coverage_rows)
    recommendations = build_recommendations(findings)
    dates = sorted({s.prediction_date for s in samples if s.prediction_date})
    return ConfidenceCalibrationArtifact(SCHEMA_VERSION, datetime.now(timezone.utc).replace(microsecond=0).isoformat(), calibration_input.input_summary, {"prediction_date_start": dates[0] if dates else None, "prediction_date_end": dates[-1] if dates else None, "target_date_count": len({s.target_date for s in samples if s.target_date})}, {"total_samples": len(samples), "direction_usable_samples": sum(1 for s in samples if s.direction_hit is not None), "high_low_usable_samples": sum(1 for s in samples if s.predicted_high is not None and s.predicted_low is not None), "insufficient_sample_handled": True}, bucket_rows, overall, rating_rows, action_rows, high_low, coverage_rows, [f.to_dict() for f in findings], [r.to_dict() for r in recommendations], dict(FORBIDDEN_FALSE, advisory_only=True, production_mutation_allowed=False, no_forbidden_actions_performed=True), {"ai_dev_122": "Consumes prediction/evaluation/source coverage history when available.", "ai_dev_123": "Can attach source/evidence IDs for explainability-aware calibration.", "ai_dev_125": "Provides advisory findings for future adaptive weight recommendation research only.", "ai_dev_126": "Dashboard warnings may be considered in a later task after approval.", "backtesting_py": "Offline strategy research may consume artifact; no automatic strategy change."})
def input_from_payload(payload: dict[str, Any]) -> CalibrationInput: return input_from_dict(payload)
