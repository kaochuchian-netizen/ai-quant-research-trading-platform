"""Safe structured-card diagnostics. Never serialize exception args or locals."""
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path

SCHEMA = "structured_card_failure_v1"
CATEGORIES = {
    "market_data_missing": "行情資料尚未取得",
    "historical_data_invalid": "歷史資料未通過檢核",
    "structured_card_validation_failed": "決策資料檢核未通過",
    "analysis_failed": "分析未完成",
    "news_evidence_insufficient": "新聞證據不足",
}
VALIDATIONS = {
    "prediction_interval_incomplete": ["prediction_range.low", "prediction_range.high"],
    "prediction_interval_reversed": ["prediction_range.low", "prediction_range.high"],
    "next_session_interval_incomplete": ["next_session_range.low", "next_session_range.high"],
    "next_session_interval_reversed": ["next_session_range.low", "next_session_range.high"],
    "unsupported_tw_prediction_window": ["window"],
    "same_horizon_semantic_conflict": ["direction", "reasoning.directional_markers", "signal_conflict"],
    "missing_or_unsupported_today_direction": ["presentation.direction"],
    "missing_or_unsupported_prediction_direction": ["snapshot.direction_forecast"],
    "same_horizon_direction_conflict": ["presentation.direction", "snapshot.direction_forecast"],
    "invalid_prediction_interval": ["prediction_range.low", "prediction_range.high"],
    "missing_prediction_target": ["point_forecast.price"],
    "prediction_target_outside_interval": ["point_forecast.price", "prediction_range.low", "prediction_range.high"],
    "renderer_or_non_prediction_owned_target": ["point_forecast.owner"],
    "prediction_target_execution_alias": ["point_forecast.is_execution_target"],
    "prediction_range_support_resistance_alias": ["point_forecast.is_support", "point_forecast.is_resistance"],
    "confidence_semantic_aliasing": ["snapshot.confidence_owner"],
    "negative_news_funnel_count": ["news.retrieved_count", "news.qualified_count", "news.selected_count"],
    "news_qualified_exceeds_retrieved": ["news.retrieved_count", "news.qualified_count"],
    "news_selected_exceeds_qualified": ["news.selected_count", "news.qualified_count"],
    "news_selected_projection_count_mismatch": ["news.selected_count", "news.rendered_count"],
    "primary_news_limit_exceeded": ["news.rendered_count"],
    "selected_news_missing_identity": ["news.identity_present"],
    "selected_news_missing_title": ["news.title_present"],
    "selected_news_missing_source": ["news.source_present"],
    "selected_news_missing_provenance": ["news.provenance_present"],
    "selected_news_missing_attribution": ["news.attribution_present"],
}
SAFE_ENUMS = {"bullish", "bearish", "neutral", "range_bound", "insufficient_evidence",
              "BULLISH", "BEARISH", "NEUTRAL", "tw_prediction_engine", "prediction_model",
              "pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"}
HISTORICAL_CODES = {"STALE", "INSUFFICIENT_LOOKBACK", "INVALID_GEOMETRY", "DUPLICATE_DATE", "FUTURE_DATA", "PARSER_ERROR", "EMPTY", "SOURCE_FAILED", "ADMISSION_REJECTED", "historical_csv_missing", "historical_csv_insufficient", "historical_bootstrap_failed"}
STAGES = {"ANALYSIS", "HISTORICAL_INDICATORS", "ADR_ANALYSIS", "NEWS_ANALYSIS", "CHIP_ANALYSIS",
          "SCORE_ANALYSIS", "STOCK_ANALYSIS", "REPORT_FORMAT", "SQLITE_WRITE",
          "STRUCTURED_CARD_BUILD", "NEWS_EVIDENCE", "TACTICAL_UPGRADE",
          "RESEARCH_PREDICTION", "PREDICTION_PROJECTION", "PRODUCT_PROJECTION",
          "ARTIFACT_WRITE", "MANUAL_PROGRESS_WRITE"}
def _safe(value):
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) else "NON_FINITE"
    if isinstance(value, str) and value in SAFE_ENUMS:
        return value
    return "REDACTED"

class CardValidationError(ValueError):
    """ValueError-compatible contract rejection with allowlisted field evidence."""
    def __init__(self, codes, *, values=None):
        codes = [codes] if isinstance(codes, str) else codes
        self.validation_codes = sorted(set(c for c in codes if c in VALIDATIONS))
        self.validation_fields = sorted({f for c in self.validation_codes for f in VALIDATIONS[c]})
        self.validation_values = {k: _safe(v) for k, v in (values or {}).items() if k in self.validation_fields}
        super().__init__("|".join(self.validation_codes) or "structured_card_validation_failed")

@contextmanager
def card_stage(stage):
    try:
        yield
    except Exception as exc:
        if not hasattr(exc, "card_substage"):
            exc.card_substage = stage if stage in STAGES else "STRUCTURED_CARD_BUILD"
        raise

def failure_diagnostic(exc, *, stage="ANALYSIS", symbol="", run_id=""):
    stage = stage if stage in STAGES else "ANALYSIS"
    substage = getattr(exc, "card_substage", stage)
    substage = substage if substage in STAGES else stage
    structured = substage in {"STRUCTURED_CARD_BUILD", "NEWS_EVIDENCE", "TACTICAL_UPGRADE",
                             "RESEARCH_PREDICTION", "PREDICTION_PROJECTION", "PRODUCT_PROJECTION"}
    category = "structured_card_validation_failed" if structured and isinstance(exc, ValueError) else "analysis_failed"
    if stage == "HISTORICAL_INDICATORS":
        category = "market_data_missing" if isinstance(exc, FileNotFoundError) else "historical_data_invalid"
    codes = list(exc.validation_codes) if isinstance(exc, CardValidationError) else []
    fields = list(exc.validation_fields) if isinstance(exc, CardValidationError) else []
    values = dict(exc.validation_values) if isinstance(exc, CardValidationError) else {}
    frames = []
    tb = exc.__traceback__
    while tb:
        code = tb.tb_frame.f_code
        # No source lines, absolute paths, locals, exception args or chained messages.
        frames.append({"file": Path(code.co_filename).name, "function": code.co_name, "line": tb.tb_lineno})
        tb = tb.tb_next
    result = {"schema_version": SCHEMA, "category": category,
              "reason_code": codes[0] if codes else category, "validation_codes": codes,
              "stage": stage, "substage": substage, "validation_fields": fields,
              "validation_values": values, "safe_exception_message": "|".join(codes) if codes else "Exception details withheld; inspect safe frame evidence",
              "exception_type": type(exc).__name__, "traceback_frames": frames,
              "symbol": symbol if str(symbol).isdigit() else "REDACTED",
              "run_identity_digest": hashlib.sha256(str(run_id).encode()).hexdigest()}
    result["diagnostic_id"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result
