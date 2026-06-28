#!/usr/bin/env python3
"""Export prediction quality review results into dashboard/report payloads."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/dashboard_prediction_review_export_input.example.json")
SCHEMA_VERSION = "dashboard_prediction_review_report_export_v1"
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
    "deployed_dashboard": False,
    "modified_forecast_runtime_weights": False,
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


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def pct(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value * 100:.1f}%"
    return "n/a"


def source(data: dict[str, Any]) -> dict[str, Any]:
    value = data.get("source_prediction_quality_review")
    return value if isinstance(value, dict) else {}


def insufficient(summary: dict[str, Any]) -> bool:
    return summary.get("overall_quality_status") == "insufficient_data" or summary.get("overall_quality_grade") == "Insufficient Data"


def overall_quality_card(summary: dict[str, Any]) -> dict[str, Any]:
    warning = "資料不足，不應過度解讀命中率"
    warnings = [warning] if insufficient(summary) else []
    return {
        "card_id": "overall_quality_card",
        "card_type": "forecast_quality",
        "title": "Forecast Quality",
        "status": summary.get("overall_quality_status"),
        "grade": summary.get("overall_quality_grade"),
        "summary_text": (
            f"Overall forecast quality is {summary.get('overall_quality_grade')} "
            f"with {summary.get('evaluated_records', 0)} evaluated records."
        ),
        "metrics": {
            "total_records": summary.get("total_records"),
            "evaluated_records": summary.get("evaluated_records"),
            "pending_records": summary.get("pending_records"),
            "interval_hit_rate": summary.get("overall_interval_hit_rate"),
            "direction_hit_rate": summary.get("overall_direction_hit_rate"),
            "mean_absolute_error_pct": summary.get("overall_mean_absolute_error_pct"),
        },
        "warnings": warnings,
        "drilldown_refs": ["horizon_quality_cards", "confidence_calibration_card", "top_error_patterns_card"],
    }


def horizon_quality_cards(horizon_reviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for review in horizon_reviews:
        horizon = str(review.get("horizon"))
        risk_note = "資料不足，不應過度解讀命中率" if review.get("quality_status") == "insufficient_data" else "Review trend and interval misses before tuning."
        cards.append({
            "card_id": f"horizon_quality_{horizon}",
            "card_type": "horizon_quality",
            "title": f"{horizon} Quality",
            "horizon": horizon,
            "quality_grade": review.get("quality_grade"),
            "quality_status": review.get("quality_status"),
            "evaluated_records": review.get("evaluated_records"),
            "pending_records": review.get("pending_records"),
            "interval_hit_rate": review.get("interval_hit_rate"),
            "direction_hit_rate": review.get("direction_hit_rate"),
            "mean_absolute_error_pct": review.get("mean_absolute_error_pct"),
            "summary_text": (
                f"{horizon} has {review.get('evaluated_records', 0)} evaluated and "
                f"{review.get('pending_records', 0)} pending records."
            ),
            "risk_note": risk_note,
        })
    return cards


def confidence_card(calibrations: list[dict[str, Any]]) -> dict[str, Any]:
    over = [item["bucket"] for item in calibrations if item.get("calibration_status") == "overconfident"]
    under = [item["bucket"] for item in calibrations if item.get("calibration_status") == "underconfident"]
    insufficient_buckets = [item["bucket"] for item in calibrations if item.get("calibration_status") == "insufficient_data"]
    return {
        "card_id": "confidence_calibration_card",
        "card_type": "confidence_calibration",
        "title": "Confidence Calibration",
        "bucket_count": len(calibrations),
        "calibration_summary": calibrations,
        "overconfident_buckets": over,
        "underconfident_buckets": under,
        "insufficient_data_buckets": insufficient_buckets,
        "calibration_notes": [
            "Buckets below minimum sample count remain insufficient.",
            "Calibration is review-only and does not update forecast runtime weights.",
        ],
    }


def error_patterns_card(patterns: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "card_id": "top_error_patterns_card",
        "card_type": "top_error_patterns",
        "title": "Top Error Patterns",
        "top_patterns": patterns[:5],
        "pattern_count": len(patterns),
        "affected_horizons": sorted({horizon for pattern in patterns for horizon in pattern.get("affected_horizons", [])}),
        "severity": [pattern.get("severity") for pattern in patterns[:5]],
        "example_record_ids": [record_id for pattern in patterns[:5] for record_id in pattern.get("example_record_ids", [])],
        "recommendations": [pattern.get("recommendation") for pattern in patterns[:5]],
    }


def improvement_card(recommendations: list[dict[str, Any]], hints: list[dict[str, Any]]) -> dict[str, Any]:
    priorities: dict[str, int] = {}
    for item in recommendations:
        priority = str(item.get("priority", "unknown"))
        priorities[priority] = priorities.get(priority, 0) + 1
    return {
        "card_id": "daily_improvement_card",
        "card_type": "daily_improvement",
        "title": "Daily Improvement",
        "recommendations": recommendations,
        "priority_summary": priorities,
        "human_review_required_count": sum(1 for item in recommendations if item.get("requires_human_review") is True),
        "safe_to_apply_automatically_count": sum(1 for item in recommendations if item.get("safe_to_apply_automatically") is True),
        "next_forecast_tuning_hints": hints,
    }


def pending_card(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "card_id": "pending_actuals_card",
        "card_type": "pending_actuals",
        "title": "Pending Actual Outcomes",
        "status": "coverage_limited" if summary.get("pending_records", 0) else "complete",
        "pending_records": summary.get("pending_records"),
        "total_records": summary.get("total_records"),
        "summary_text": f"{summary.get('pending_records', 0)} records are still pending actual outcome coverage.",
        "warnings": ["Pending records are excluded from hit-rate denominators."],
    }


def safety_card() -> dict[str, Any]:
    return {
        "card_id": "safety_status_card",
        "card_type": "safety_status",
        "title": "Safety Status",
        "advisory_only": True,
        "no_trading": True,
        "no_notification": True,
        "no_production_db_write": True,
        "no_runtime_weight_change": True,
        "fixture_only": True,
    }


def dashboard_payload(data: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    summary = src.get("quality_review_summary", {}) if isinstance(src.get("quality_review_summary"), dict) else {}
    horizons = src.get("horizon_reviews", []) if isinstance(src.get("horizon_reviews"), list) else []
    calibrations = src.get("confidence_calibration", []) if isinstance(src.get("confidence_calibration"), list) else []
    patterns = src.get("error_patterns", []) if isinstance(src.get("error_patterns"), list) else []
    recommendations = src.get("daily_improvement_recommendations", []) if isinstance(src.get("daily_improvement_recommendations"), list) else []
    hints = src.get("next_forecast_tuning_hints", []) if isinstance(src.get("next_forecast_tuning_hints"), list) else []
    cards = [
        overall_quality_card(summary),
        *horizon_quality_cards(horizons),
        confidence_card(calibrations),
        error_patterns_card(patterns),
        improvement_card(recommendations, hints),
        pending_card(summary),
        safety_card(),
    ]
    config = data.get("dashboard_config") if isinstance(data.get("dashboard_config"), dict) else {}
    return {
        "dashboard_version": config.get("dashboard_version", "dashboard_prediction_review_export_v1"),
        "generated_for": "prediction_review_dashboard",
        "cards": cards,
        "sections": {
            "forecast_quality": ["overall_quality_card", "horizon_quality_cards"],
            "calibration": ["confidence_calibration_card"],
            "errors": ["top_error_patterns_card"],
            "improvement": ["daily_improvement_card"],
            "safety": ["pending_actuals_card", "safety_status_card"],
        },
        "badges": {
            "advisory_only": True,
            "fixture_only": True,
            "insufficient_data": insufficient(summary),
        },
    }


def section(section_id: str, title: str, priority: str, markdown: str, machine: dict[str, Any], refs: list[str]) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "title": title,
        "priority": priority,
        "markdown": markdown,
        "machine_readable": machine,
        "source_refs": refs,
        "advisory_only": True,
    }


def report_payload(data: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    summary = src.get("quality_review_summary", {}) if isinstance(src.get("quality_review_summary"), dict) else {}
    horizons = src.get("horizon_reviews", []) if isinstance(src.get("horizon_reviews"), list) else []
    calibrations = src.get("confidence_calibration", []) if isinstance(src.get("confidence_calibration"), list) else []
    patterns = src.get("error_patterns", []) if isinstance(src.get("error_patterns"), list) else []
    recommendations = src.get("daily_improvement_recommendations", []) if isinstance(src.get("daily_improvement_recommendations"), list) else []
    hints = src.get("next_forecast_tuning_hints", []) if isinstance(src.get("next_forecast_tuning_hints"), list) else []
    report_config = data.get("report_config") if isinstance(data.get("report_config"), dict) else {}
    sections = [
        section(
            "executive_summary",
            "Executive Summary",
            "high",
            (
                f"Current quality status is `{summary.get('overall_quality_status')}` with "
                f"{summary.get('evaluated_records', 0)} evaluated records. "
                f"{'資料不足，不應過度解讀命中率。' if insufficient(summary) else 'Sample coverage is sufficient for review.'} "
                "Human review is required before any forecast tuning."
            ),
            {"quality_review_summary": summary},
            ["quality_review_summary"],
        ),
        section(
            "forecast_quality_summary",
            "Forecast Quality Summary",
            "high",
            f"Overall grade: `{summary.get('overall_quality_grade')}`; interval hit rate: `{pct(summary.get('overall_interval_hit_rate'))}`.",
            {"overall_quality_grade": summary.get("overall_quality_grade"), "overall_interval_hit_rate": summary.get("overall_interval_hit_rate")},
            ["quality_review_summary"],
        ),
        section(
            "horizon_review_summary",
            "Horizon Review Summary",
            "medium",
            "Horizon cards summarize evaluated records, pending records, hit rates, and error rates.",
            {"horizon_reviews": horizons},
            ["horizon_reviews"],
        ),
        section(
            "confidence_calibration_summary",
            "Confidence Calibration Summary",
            "medium",
            "Confidence buckets below sample thresholds remain insufficient for calibration conclusions.",
            {"confidence_calibration": calibrations},
            ["confidence_calibration"],
        ),
        section(
            "error_pattern_summary",
            "Error Pattern Summary",
            "medium",
            f"Detected {len(patterns)} top error pattern groups.",
            {"error_patterns": patterns},
            ["error_patterns"],
        ),
        section(
            "daily_improvement_recommendations",
            "Daily Improvement Recommendations",
            "high",
            "Recommendations are advisory only, require human review, and are not applied automatically.",
            {"recommendations": recommendations, "next_forecast_tuning_hints": hints},
            ["daily_improvement_recommendations", "next_forecast_tuning_hints"],
        ),
        section(
            "risk_and_limitations",
            "Risk And Limitations",
            "high",
            (
                "樣本數不足時不得過度解讀。 Fixture-only result 不代表 production performance。 "
                "Review recommendations 不會自動修改 forecast weights。 本輸出不構成投資建議。"
            ),
            {
                "insufficient_data_warning": "樣本數不足時不得過度解讀",
                "fixture_only_not_production_performance": True,
                "forecast_weights_not_modified": True,
                "not_investment_advice": True,
            },
            ["safety", "quality_review_summary"],
        ),
        section(
            "next_steps",
            "Next Steps",
            "medium",
            "Use this export as input for a future Daily Report Forecast Review Section or Dashboard MVP task.",
            {"next_recommendation": "AI-DEV-075 Daily Report Forecast Review Section V1"},
            ["next_recommendation"],
        ),
    ]
    return {
        "report_version": report_config.get("report_version", "prediction_review_report_export_v1"),
        "generated_for": "daily_report_prediction_review",
        "include_markdown_summary": report_config.get("include_markdown_summary", True),
        "include_machine_readable_sections": report_config.get("include_machine_readable_sections", True),
        "include_dashboard_links_placeholder": report_config.get("include_dashboard_links_placeholder", True),
        "sections": sections,
    }


def export_summary(dashboard: dict[str, Any], report: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    cards = dashboard.get("cards", [])
    sections = report.get("sections", [])
    insufficient_cards = [
        card.get("card_id")
        for card in cards
        if "資料不足，不應過度解讀命中率" in json.dumps(card, ensure_ascii=False)
    ]
    return {
        "card_count": len(cards),
        "supported_cards": [card.get("card_id") for card in cards],
        "insufficient_data_cards": insufficient_cards,
        "advisory_only": True,
        "section_count": len(sections),
        "supported_sections": [section.get("section_id") for section in sections],
        "markdown_sections_count": sum(1 for section in sections if section.get("markdown")),
        "machine_readable_sections_count": sum(1 for section in sections if isinstance(section.get("machine_readable"), dict)),
        "source_quality_status": src.get("quality_review_summary", {}).get("overall_quality_status") if isinstance(src.get("quality_review_summary"), dict) else None,
    }


def decision(summary: dict[str, Any], src: dict[str, Any]) -> str:
    quality = src.get("quality_review_summary", {}) if isinstance(src.get("quality_review_summary"), dict) else {}
    if not quality or quality.get("total_records", 0) == 0:
        return "no_review_records"
    if summary.get("insufficient_data_cards"):
        return "dashboard_report_export_completed_with_insufficient_data"
    return "dashboard_report_export_completed"


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    src = source(data)
    dashboard = dashboard_payload(data, src)
    report = report_payload(data, src)
    summary = export_summary(dashboard, report, src)
    result_decision = decision(summary, src)
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-074"),
        "run_id": data.get("run_id", "dashboard-prediction-review-export-fixture"),
        "generated_at": data.get("generated_at") or now_iso(),
        "mode": "fixture_dry_run",
        "input_summary": {
            "source_schema_version": src.get("schema_version"),
            "source_run_id": src.get("run_id"),
            "source_decision": src.get("decision"),
            "dashboard_version": data.get("dashboard_config", {}).get("dashboard_version") if isinstance(data.get("dashboard_config"), dict) else None,
            "report_version": data.get("report_config", {}).get("report_version") if isinstance(data.get("report_config"), dict) else None,
            "source_side_effects": deepcopy(src.get("side_effects", {})),
        },
        "dashboard_payload": dashboard,
        "report_payload": report,
        "export_summary": summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": {
            "fixture_only": True,
            "repo_only": True,
            "advisory_only": True,
            "no_trading": True,
            "no_notification": True,
            "no_production_db_write": True,
            "no_runtime_weight_change": True,
            "dashboard_deployed": False,
        },
        "ok": result_decision in {
            "dashboard_report_export_completed",
            "dashboard_report_export_completed_with_insufficient_data",
            "no_review_records",
        },
        "decision": result_decision,
        "next_recommendation": "AI-DEV-075 Daily Report Forecast Review Section V1",
    }


def write_result(result: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(result, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if pretty:
        rendered += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export prediction quality review result for dashboard/report fixtures.")
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
