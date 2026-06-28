#!/usr/bin/env python3
"""Backfill fixture actual outcomes and evaluate forecast review records.

This helper is repo-only and fixture-only. It reads explicit JSON input,
calculates deterministic actual outcomes and evaluation metrics, then writes a
sanitized result artifact. It does not call external APIs or production
runtimes.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_forecast_actual_outcome_backfill_input.example.json")
SCHEMA_VERSION = "daily_report_forecast_actual_outcome_backfill_evaluation_v1"
ALLOWED_HORIZONS = {"same_day", "next_day", "one_month"}
PENDING_STATUS = "pending_actual_outcome"
EVALUATED_STATUS = "evaluated"

SIDE_EFFECTS = {
    "read_secrets": False,
    "called_external_ai_runtime": False,
    "called_market_data_runtime": False,
    "sent_notification": False,
    "placed_trade_order": False,
    "modified_production_db": False,
    "modified_cron_systemd_timer": False,
    "modified_n8n": False,
    "mutated_github_issue": False,
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("input JSON root must be an object")
    return data


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    text = str(value)
    if len(text) >= 10:
        text = text[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def round_or_none(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def confidence_bucket(confidence: Any) -> str:
    numeric = as_float(confidence)
    if numeric is None:
        return "unknown"
    if 0 <= numeric <= 1:
        numeric *= 100
    if numeric <= 20:
        return "0-20"
    if numeric <= 40:
        return "21-40"
    if numeric <= 60:
        return "41-60"
    if numeric <= 80:
        return "61-80"
    if numeric <= 100:
        return "81-100"
    return "unknown"


def normalize_horizon(record: dict[str, Any]) -> str:
    return str(record.get("horizon") or record.get("forecast_horizon") or "")


def normalize_forecast(record: dict[str, Any]) -> dict[str, Any]:
    forecast = record.get("forecast")
    if isinstance(forecast, dict):
        return deepcopy(forecast)
    snapshot = record.get("forecast_snapshot")
    if not isinstance(snapshot, dict):
        return {}
    result: dict[str, Any] = {
        "forecast_type": snapshot.get("forecast_type"),
        "confidence": snapshot.get("confidence_score"),
        "confidence_bucket": snapshot.get("confidence_bucket"),
        "basis": deepcopy(snapshot.get("basis", [])),
    }
    if isinstance(snapshot.get("price_interval"), dict):
        result["price_interval"] = deepcopy(snapshot["price_interval"])
    if isinstance(snapshot.get("trend_interval"), dict):
        result["trend_interval"] = deepcopy(snapshot["trend_interval"])
    if "trend" in snapshot:
        result["trend"] = snapshot.get("trend")
    return result


def normalize_review_record(record: dict[str, Any]) -> dict[str, Any]:
    forecast = normalize_forecast(record)
    confidence = record.get("confidence", forecast.get("confidence"))
    horizon = normalize_horizon(record)
    return {
        "record_id": str(record.get("record_id", "")),
        "stock_id": str(record.get("stock_id", "")),
        "stock_name": str(record.get("stock_name", "")),
        "forecast_version": record.get("forecast_version"),
        "run_date": record.get("run_date"),
        "horizon": horizon,
        "target_date": record.get("target_date"),
        "target_window_start": record.get("target_window_start") or record.get("run_date"),
        "target_window_end": record.get("target_window_end") or record.get("target_date"),
        "forecast": forecast,
        "confidence": confidence,
        "signals": deepcopy(record.get("signals") or record.get("source_metadata", {}).get("signals_used", [])),
        "status": record.get("status") or record.get("record_status") or PENDING_STATUS,
        "advisory_only": record.get("advisory_only", record.get("safety", {}).get("advisory_only", True)),
    }


def market_index(market_actuals: list[Any]) -> dict[str, dict[str, dict[str, Any]]]:
    index: dict[str, dict[str, dict[str, Any]]] = {}
    for item in market_actuals:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        if source not in {"fixture", "repo_example"}:
            continue
        stock_id = str(item.get("stock_id", ""))
        actual_date = str(item.get("date", ""))
        if not stock_id or not parse_date(actual_date):
            continue
        values = {key: as_float(item.get(key)) for key in ["open", "high", "low", "close", "volume"]}
        if any(values[key] is None for key in ["open", "high", "low", "close"]):
            continue
        index.setdefault(stock_id, {})[actual_date[:10]] = {**item, **values}
    return index


def next_trading_actual(stock_actuals: dict[str, dict[str, Any]], run_date: Any) -> tuple[str | None, dict[str, Any] | None]:
    base = parse_date(run_date)
    if base is None:
        return None, None
    candidates = sorted(
        (actual_date, actual)
        for actual_date, actual in stock_actuals.items()
        if (parsed := parse_date(actual_date)) is not None and parsed > base
    )
    return candidates[0] if candidates else (None, None)


def window_actuals(
    stock_actuals: dict[str, dict[str, Any]],
    start: Any,
    end: Any,
) -> list[tuple[str, dict[str, Any]]]:
    start_date = parse_date(start)
    end_date = parse_date(end)
    if start_date is None or end_date is None:
        return []
    return sorted(
        (actual_date, actual)
        for actual_date, actual in stock_actuals.items()
        if (parsed := parse_date(actual_date)) is not None and start_date <= parsed <= end_date
    )


def actual_trend(return_pct: float | None) -> str:
    if return_pct is None:
        return "unknown"
    if return_pct > 0.03:
        return "up"
    if return_pct < -0.03:
        return "down"
    return "flat"


def forecast_trend(record: dict[str, Any]) -> str | None:
    trend = str(record.get("forecast", {}).get("trend", "")).lower()
    if trend in {"up", "positive", "mildly_positive", "bullish"}:
        return "up"
    if trend in {"down", "negative", "mildly_negative", "bearish"}:
        return "down"
    if trend in {"flat", "neutral", "sideways"}:
        return "flat"
    interval = record.get("forecast", {}).get("trend_interval")
    if isinstance(interval, dict):
        lower = as_float(interval.get("lower"))
        upper = as_float(interval.get("upper"))
        if lower is not None and upper is not None:
            midpoint = (lower + upper) / 2
            return actual_trend(midpoint)
    return None


def price_interval(record: dict[str, Any]) -> tuple[float | None, float | None]:
    interval = record.get("forecast", {}).get("price_interval")
    if not isinstance(interval, dict):
        return None, None
    return as_float(interval.get("low")), as_float(interval.get("high"))


def interval_error_pct(actual: float | None, low: float | None, high: float | None) -> float | None:
    if actual is None or low is None or high is None or actual == 0:
        return None
    if low <= actual <= high:
        return 0.0
    boundary = low if actual < low else high
    return abs(actual - boundary) / abs(actual)


def evaluate_record(record: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    low, high = price_interval(record)
    horizon = record["horizon"]
    actual_high = as_float(actual.get("actual_high") or actual.get("actual_window_high"))
    actual_low = as_float(actual.get("actual_low") or actual.get("actual_window_low"))
    actual_close = as_float(actual.get("actual_close") or actual.get("actual_end_close"))
    high_hit = low is not None and high is not None and actual_high is not None and low <= actual_high <= high
    low_hit = low is not None and high is not None and actual_low is not None and low <= actual_low <= high
    close_hit = low is not None and high is not None and actual_close is not None and low <= actual_close <= high
    errors = [
        value
        for value in [
            interval_error_pct(actual_high, low, high),
            interval_error_pct(actual_low, low, high),
            interval_error_pct(actual_close, low, high),
        ]
        if value is not None
    ]
    direction_hit: bool | None = None
    skipped_reason: str | None = None
    if horizon == "one_month":
        expected = forecast_trend(record)
        direction_hit = expected is not None and expected == actual.get("actual_trend")
        if expected is None:
            skipped_reason = "no_direction_forecast"
    else:
        skipped_reason = "no_direction_forecast"
    range_width_pct = None
    if low is not None and high is not None and actual_close not in {None, 0}:
        range_width_pct = (high - low) / abs(float(actual_close))
    return {
        "interval_hit": high_hit and low_hit if low is not None and high is not None else None,
        "high_interval_hit": high_hit if low is not None and high is not None else None,
        "low_interval_hit": low_hit if low is not None and high is not None else None,
        "close_in_interval": close_hit if low is not None and high is not None else None,
        "direction_hit": direction_hit,
        "absolute_error": round_or_none(statistics.mean(errors) if errors else None),
        "absolute_error_pct": round_or_none(statistics.mean(errors) if errors else None),
        "range_width_pct": round_or_none(range_width_pct),
        "confidence_bucket": confidence_bucket(record.get("confidence")),
        "evaluation_status": EVALUATED_STATUS,
        "skipped_reason": skipped_reason,
    }


def pending_record(record: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        **record,
        "status": PENDING_STATUS,
        "pending_reason": reason,
        "actual_outcome": {"outcome_status": "pending", "pending_reason": reason},
        "evaluation_metrics": {
            "evaluation_status": "pending",
            "confidence_bucket": confidence_bucket(record.get("confidence")),
            "skipped_reason": reason,
        },
    }


def backfill_record(record: dict[str, Any], actuals: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    stock_actuals = actuals.get(record["stock_id"], {})
    horizon = record["horizon"]
    if horizon == "same_day":
        target_date = str(record.get("target_date", ""))[:10]
        actual = stock_actuals.get(target_date)
        if actual is None:
            return pending_record(record, "missing_target_date_actual")
        outcome = {
            "target_date": target_date,
            "actual_high": actual["high"],
            "actual_low": actual["low"],
            "actual_close": actual["close"],
            "source": actual["source"],
        }
    elif horizon == "next_day":
        target_date, actual = next_trading_actual(stock_actuals, record.get("run_date"))
        if actual is None or target_date is None:
            return pending_record(record, "missing_next_trading_day_actual")
        outcome = {
            "target_date": target_date,
            "actual_high": actual["high"],
            "actual_low": actual["low"],
            "actual_close": actual["close"],
            "source": actual["source"],
        }
    elif horizon == "one_month":
        rows = window_actuals(stock_actuals, record.get("target_window_start"), record.get("target_window_end"))
        if len(rows) < 2:
            return pending_record(record, "insufficient_window_actuals")
        first = rows[0][1]
        last = rows[-1][1]
        start_close = first["close"]
        end_close = last["close"]
        return_pct = (end_close - start_close) / start_close if start_close else None
        window_high = max(row["high"] for _, row in rows)
        window_low = min(row["low"] for _, row in rows)
        outcome = {
            "target_window_start": rows[0][0],
            "target_window_end": rows[-1][0],
            "actual_window_high": window_high,
            "actual_window_low": window_low,
            "actual_start_close": start_close,
            "actual_end_close": end_close,
            "actual_return_pct": round_or_none(return_pct),
            "actual_trend": actual_trend(return_pct),
            "max_upside_pct": round_or_none((window_high - start_close) / start_close if start_close else None),
            "max_drawdown_pct": round_or_none((window_low - start_close) / start_close if start_close else None),
            "source": sorted({row["source"] for _, row in rows}),
        }
    else:
        return pending_record(record, "unsupported_horizon")
    metrics = evaluate_record(record, outcome)
    return {
        **record,
        "status": EVALUATED_STATUS,
        "actual_outcome": {"outcome_status": "available", "values": outcome},
        **outcome,
        "evaluation_metrics": metrics,
    }


def rate(records: list[dict[str, Any]], metric: str) -> float | None:
    values = [record.get("evaluation_metrics", {}).get(metric) for record in records]
    values = [value for value in values if isinstance(value, bool)]
    if not values:
        return None
    return round(sum(1 for value in values if value) / len(values), 6)


def mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 6) if values else None


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 6) if values else None


def aggregate_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [record for record in records if record.get("status") == EVALUATED_STATUS]
    pending = [record for record in records if record.get("status") == PENDING_STATUS]
    abs_errors = [
        record["evaluation_metrics"]["absolute_error_pct"]
        for record in evaluated
        if isinstance(record.get("evaluation_metrics", {}).get("absolute_error_pct"), (int, float))
    ]
    coverage_by_horizon = {}
    for horizon in sorted(ALLOWED_HORIZONS):
        horizon_records = [record for record in records if record.get("horizon") == horizon]
        horizon_evaluated = [record for record in horizon_records if record.get("status") == EVALUATED_STATUS]
        coverage_by_horizon[horizon] = {
            "total": len(horizon_records),
            "evaluated": len(horizon_evaluated),
            "pending": len(horizon_records) - len(horizon_evaluated),
            "coverage_rate": round(len(horizon_evaluated) / len(horizon_records), 6) if horizon_records else None,
        }
    pending_by_reason: dict[str, int] = {}
    for record in pending:
        reason = str(record.get("pending_reason", "unknown"))
        pending_by_reason[reason] = pending_by_reason.get(reason, 0) + 1
    bucket_metrics: dict[str, dict[str, Any]] = {}
    for bucket in ["0-20", "21-40", "41-60", "61-80", "81-100", "unknown"]:
        bucket_records = [record for record in records if record.get("evaluation_metrics", {}).get("confidence_bucket") == bucket]
        bucket_eval = [record for record in bucket_records if record.get("status") == EVALUATED_STATUS]
        bucket_metrics[bucket] = {
            "total_records": len(bucket_records),
            "evaluated_records": len(bucket_eval),
            "interval_hit_rate": rate(bucket_eval, "interval_hit"),
            "direction_hit_rate": rate(bucket_eval, "direction_hit"),
            "mean_absolute_error_pct": mean([
                metric
                for record in bucket_eval
                if isinstance((metric := record.get("evaluation_metrics", {}).get("absolute_error_pct")), (int, float))
            ]),
        }
    return {
        "total_records": len(records),
        "evaluated_records": len(evaluated),
        "pending_records": len(pending),
        "same_day_count": sum(1 for record in records if record.get("horizon") == "same_day"),
        "next_day_count": sum(1 for record in records if record.get("horizon") == "next_day"),
        "one_month_count": sum(1 for record in records if record.get("horizon") == "one_month"),
        "interval_hit_rate": rate(evaluated, "interval_hit"),
        "high_interval_hit_rate": rate(evaluated, "high_interval_hit"),
        "low_interval_hit_rate": rate(evaluated, "low_interval_hit"),
        "direction_hit_rate": rate(evaluated, "direction_hit"),
        "mean_absolute_error_pct": mean(abs_errors),
        "median_absolute_error_pct": median(abs_errors),
        "coverage_by_horizon": coverage_by_horizon,
        "pending_by_reason": pending_by_reason,
        "confidence_bucket_metrics": bucket_metrics,
    }


def decision(metrics: dict[str, Any]) -> str:
    if metrics["total_records"] == 0 or metrics["evaluated_records"] == 0:
        return "no_evaluable_records"
    if metrics["pending_records"] > 0:
        return "partial_pending_actuals"
    return "backfill_evaluation_completed"


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    input_records = data.get("review_records", [])
    if not isinstance(input_records, list):
        input_records = []
    records = [normalize_review_record(record) for record in input_records if isinstance(record, dict)]
    actuals = market_index(data.get("market_actuals", []) if isinstance(data.get("market_actuals"), list) else [])
    result_records = [backfill_record(record, actuals) for record in records if record.get("horizon") in ALLOWED_HORIZONS]
    metrics = aggregate_metrics(result_records)
    result_decision = decision(metrics)
    ok = result_decision in {"backfill_evaluation_completed", "partial_pending_actuals", "no_evaluable_records"}
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-072"),
        "run_id": data.get("run_id", "daily-report-forecast-actual-outcome-backfill-fixture"),
        "generated_at": data.get("generated_at") or now_iso(),
        "mode": "fixture_dry_run",
        "input_summary": {
            "forecast_version": data.get("forecast_version"),
            "review_record_count": len(records),
            "market_actual_count": len(data.get("market_actuals", [])) if isinstance(data.get("market_actuals"), list) else 0,
            "evaluation_config": deepcopy(data.get("evaluation_config", {})),
        },
        "backfill_summary": {
            "total_records": metrics["total_records"],
            "evaluated_records": metrics["evaluated_records"],
            "pending_records": metrics["pending_records"],
            "same_day_count": metrics["same_day_count"],
            "next_day_count": metrics["next_day_count"],
            "one_month_count": metrics["one_month_count"],
            "pending_by_reason": metrics["pending_by_reason"],
        },
        "evaluation_summary": {
            "interval_hit_rate": metrics["interval_hit_rate"],
            "high_interval_hit_rate": metrics["high_interval_hit_rate"],
            "low_interval_hit_rate": metrics["low_interval_hit_rate"],
            "direction_hit_rate": metrics["direction_hit_rate"],
            "mean_absolute_error_pct": metrics["mean_absolute_error_pct"],
            "median_absolute_error_pct": metrics["median_absolute_error_pct"],
        },
        "records": result_records,
        "metrics": metrics,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": {
            "fixture_only": True,
            "repo_only": True,
            "advisory_only": True,
            "research_only": True,
            "no_external_market_data": True,
            "no_external_ai_runtime": True,
            "no_notification": True,
            "no_trade": True,
            "no_order": True,
            "no_production_db": True,
        },
        "ok": ok,
        "decision": result_decision,
        "next_recommendation": "AI-DEV-073 Prediction Quality Review + Daily Improvement Loop V1",
    }


def write_result(result: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(result, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if pretty:
        rendered += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill fixture actual outcomes and evaluate forecast review records.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_result(result, Path(args.output), args.pretty)
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
