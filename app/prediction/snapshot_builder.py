"""Build advisory prediction snapshots with source coverage policy applied."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from app.prediction.schemas import SCHEMA_VERSION, PredictionSnapshot, SourceQualitySummary, normalize_confidence, unavailable
from app.prediction.source_coverage import build_source_coverage_matrix, cap_confidence, coverage_by_target
from app.prediction.source_inventory import build_data_source_inventory, inventory_by_id

def _now_parts() -> tuple[str, str]:
    now = datetime.now(timezone.utc).replace(microsecond=0); return now.date().isoformat(), now.time().isoformat().replace("+00:00", "Z")
def _normalize_prediction_value(value: Any, default_status: str = "unavailable") -> Any:
    if isinstance(value, (int, float)) and not isinstance(value, bool): return float(value)
    if isinstance(value, dict) and value.get("status"): return value
    if value in {"pending", "insufficient_data", "unavailable", "not_applicable"}: return unavailable(str(value))
    return unavailable(default_status)
def _source_quality_summary(source_ids: list[str], coverage: dict[str, Any], inventory: dict[str, dict[str, Any]]) -> SourceQualitySummary:
    primary = official = market_context = noisy = 0; notes: list[str] = []
    for source_id in source_ids:
        item = inventory.get(source_id) or {}; priority = item.get("priority")
        if priority == "A_primary": primary += 1
        elif priority == "B_official_or_company_linked": official += 1
        elif priority == "C_market_or_industry": market_context += 1
        elif priority == "D_sentiment_or_noise": noisy += 1
        if source_id == "yfinance_external_market": notes.append("yfinance is external market context only and cannot replace primary sources")
        if source_id in {"google_news_rss", "gemini_news_summary"}: notes.append("news-only evidence cannot independently raise rating")
    missing = [str(item) for item in coverage.get("missing_sources", [])]
    if missing: notes.append("missing required sources: " + ", ".join(missing))
    return SourceQualitySummary(str(coverage.get("readiness", "insufficient")), float(coverage.get("confidence_cap", 0.4)), missing, primary, official, market_context, noisy, notes)
def build_prediction_snapshot(*, run_id: str, stock_id: str, stock_name: str, prediction_target: str, predicted_high: Any = None, predicted_low: Any = None, predicted_trend: Any = None, confidence: Any = None, rating: Any = None, score: Any = None, action: Any = None, source_ids: list[str] | None = None, evidence_summary: list[str] | None = None, run_date: str | None = None, run_time: str | None = None, scheduler_window: str = "repo_fixture", pipeline_type: str = "prediction_data_foundation_v1", coverage_matrix: list[dict[str, Any]] | None = None, inventory: list[dict[str, Any]] | None = None) -> PredictionSnapshot:
    default_date, default_time = _now_parts(); source_ids = list(source_ids or ["historical_csv_fallback"]); indexed_inventory = inventory_by_id(inventory or build_data_source_inventory()); coverage_lookup = coverage_by_target(coverage_matrix or build_source_coverage_matrix(inventory=list(indexed_inventory.values()))); coverage = coverage_lookup.get(prediction_target, {"readiness": "insufficient", "coverage_score": 0, "confidence_cap": 0.4, "missing_sources": []})
    capped_confidence, confidence_status = cap_confidence(normalize_confidence(confidence), coverage); quality = _source_quality_summary(source_ids, coverage, indexed_inventory)
    review_status = "insufficient_data" if confidence_status == "insufficient_data" or coverage.get("readiness") == "insufficient" else "ready_for_evaluation"
    return PredictionSnapshot(SCHEMA_VERSION, run_id, run_date or default_date, run_time or default_time, scheduler_window, pipeline_type, str(stock_id), str(stock_name), prediction_target, _normalize_prediction_value(predicted_high), _normalize_prediction_value(predicted_low), predicted_trend if isinstance(predicted_trend, str) and predicted_trend else unavailable("not_applicable"), capped_confidence if capped_confidence is not None else unavailable("insufficient_data"), confidence_status, rating if isinstance(rating, str) and rating else unavailable("not_applicable"), float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else unavailable("not_applicable"), action if isinstance(action, str) and action else unavailable("not_applicable"), True, source_ids, list(evidence_summary or []), float(coverage.get("coverage_score", 0)), quality.to_dict(), review_status)
def build_example_prediction_snapshots() -> list[PredictionSnapshot]:
    matrix = build_source_coverage_matrix()
    return [
        build_prediction_snapshot(run_id="ai-dev-122-example-001", run_date="2026-07-02", run_time="07:00:00Z", scheduler_window="manual_fixture", stock_id="2330", stock_name="TSMC", prediction_target="next_day_high_low", predicted_high=1050.0, predicted_low=1015.0, predicted_trend="up", confidence=0.82, rating="positive", score=78.5, action="watch", source_ids=["historical_csv_fallback", "chip_analysis_existing", "adr_yfinance", "yfinance_external_market"], evidence_summary=["Local OHLCV available", "ADR/yfinance used only as confirmation", "Chip context available"], coverage_matrix=matrix),
        build_prediction_snapshot(run_id="ai-dev-122-example-002", run_date="2026-07-02", run_time="07:00:00Z", scheduler_window="manual_fixture", stock_id="00878", stock_name="ETF Example", prediction_target="three_month_trend", predicted_high="not_applicable", predicted_low="not_applicable", predicted_trend="insufficient_data", confidence=0.76, rating="neutral", score=52.0, action="hold_review", source_ids=["historical_csv_fallback", "google_news_rss", "yfinance_external_market"], evidence_summary=["ETF-specific NAV/holdings/distribution source gap", "Fundamental/disclosure sources missing", "News is metadata only"], coverage_matrix=matrix),
    ]
