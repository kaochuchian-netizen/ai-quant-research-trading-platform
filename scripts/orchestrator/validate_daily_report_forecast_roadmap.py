#!/usr/bin/env python3
"""Validate the daily report forecast roadmap package without side effects."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DOC_PATH = "docs/daily_report_forecast_roadmap.md"
CONTRACT_PATH = "templates/daily_report_forecast_contract.example.json"
REVIEW_PATH = "templates/daily_forecast_review_result.example.json"

REQUIRED_FILES = [
    DOC_PATH,
    CONTRACT_PATH,
    REVIEW_PATH,
]

REQUIRED_CONTRACT_KEYS = [
    "schema_version",
    "report_date",
    "market",
    "report_window",
    "generated_at",
    "stock_universe",
    "forecast_horizons",
    "same_day_high_low",
    "next_day_high_low",
    "one_month_trend",
    "three_month_trend",
    "confidence",
    "interval_bounds",
    "evidence_sources",
    "risk_flags",
    "no_trading_instruction",
    "research_only",
    "review_required",
    "no_order_execution",
]

REQUIRED_REVIEW_KEYS = [
    "review_date",
    "forecast_date",
    "stock_id",
    "horizon",
    "predicted_range",
    "actual_high_low",
    "direction_prediction",
    "actual_direction",
    "hit_metrics",
    "interval_coverage",
    "error_metrics",
    "evidence_quality",
    "review_status",
]

REQUIRED_HORIZONS = [
    "same_day_high_low",
    "next_day_high_low",
    "one_month_trend",
    "three_month_trend",
]

DOC_REQUIRED_PHRASES = [
    "07:00 Pre-Open Report Scope",
    "15:00 And Post-Close Review Scope",
    "same_day_high_low",
    "next_day_high_low",
    "one_month_trend",
    "three_month_trend",
    "dashboard",
    "email",
    "LINE reminder",
    "Prediction Review Lifecycle",
    "hit metrics",
    "interval coverage",
    "error metrics",
    "no orders",
    "no production pipeline changes",
    "LINE reminder only",
    "Uncertainty/confidence is required",
    "Analyst target price is low-priority sentiment metadata",
    "research-only",
    "no trading execution",
    "no personalized financial advice",
]

REQUIRED_SOURCE_PRIORITY_PHRASES = [
    "company official material information",
    "financial reports",
    "earnings calls",
    "annual and monthly revenue reports",
    "official press releases",
    "management interviews",
    "company guidance",
    "upstream/downstream industry information",
]

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def missing_keys(data: Any, keys: list[str]) -> list[str]:
    if not isinstance(data, dict):
        return keys
    return [key for key in keys if key not in data]


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(iter_strings(item))
        return result
    if isinstance(value, dict):
        result = []
        for item in value.values():
            result.extend(iter_strings(item))
        return result
    return []


def detect_secret_like_text(rel_path: str, text: str) -> list[str]:
    reasons: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            reasons.append(f"secret-like value found in {rel_path}")
            break
    return reasons


def validate_contract(data: Any) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    reasons.extend(f"contract missing key: {key}" for key in missing_keys(data, REQUIRED_CONTRACT_KEYS))
    if not isinstance(data, dict):
        return {"loaded": False}, ["contract JSON root must be an object"]

    horizons = data.get("forecast_horizons")
    if not isinstance(horizons, list):
        reasons.append("forecast_horizons must be a list")
        horizons = []
    missing_horizons = [horizon for horizon in REQUIRED_HORIZONS if horizon not in horizons]
    for horizon in missing_horizons:
        reasons.append(f"required forecast horizon missing: {horizon}")

    for key in ["research_only", "no_trading_instruction", "no_order_execution"]:
        if data.get(key) is not True:
            reasons.append(f"{key} must be true")

    for horizon in REQUIRED_HORIZONS:
        value = data.get(horizon)
        if not isinstance(value, dict):
            reasons.append(f"{horizon} must be an object")
            continue
        if value.get("horizon") != horizon:
            reasons.append(f"{horizon}.horizon must equal {horizon}")
        if "confidence" not in value:
            reasons.append(f"{horizon} missing confidence")

    for horizon in ["same_day_high_low", "next_day_high_low"]:
        value = data.get(horizon)
        if not isinstance(value, dict) or not isinstance(value.get("predicted_range"), dict):
            reasons.append(f"{horizon} must include predicted_range")
            continue
        predicted_range = value["predicted_range"]
        for bound in ["low", "high", "unit"]:
            if bound not in predicted_range:
                reasons.append(f"{horizon}.predicted_range missing {bound}")

    evidence_sources = data.get("evidence_sources")
    if not isinstance(evidence_sources, list) or not evidence_sources:
        reasons.append("evidence_sources must be a non-empty list")
    else:
        analyst_entries = [
            item for item in evidence_sources
            if isinstance(item, dict) and item.get("source_tier") == "tier_4_consensus_and_analyst"
        ]
        if analyst_entries and not any(
            item.get("usage") == "low_priority_sentiment_metadata_only" for item in analyst_entries
        ):
            reasons.append("analyst evidence must be low_priority_sentiment_metadata_only")

    return {
        "loaded": True,
        "required_keys_present": not missing_keys(data, REQUIRED_CONTRACT_KEYS),
        "required_horizons_present": not missing_horizons,
        "safety_flags_present": all(data.get(key) is True for key in [
            "research_only",
            "no_trading_instruction",
            "no_order_execution",
        ]),
    }, reasons


def validate_review(data: Any) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    reasons.extend(f"review result missing key: {key}" for key in missing_keys(data, REQUIRED_REVIEW_KEYS))
    if not isinstance(data, dict):
        return {"loaded": False}, ["review result JSON root must be an object"]

    if data.get("horizon") not in REQUIRED_HORIZONS:
        reasons.append(f"review horizon must be one of required horizons: {data.get('horizon')}")
    for key in ["hit_metrics", "interval_coverage", "error_metrics", "evidence_quality"]:
        if not isinstance(data.get(key), dict):
            reasons.append(f"{key} must be an object")

    hit_metrics = data.get("hit_metrics")
    if isinstance(hit_metrics, dict):
        for key in ["direction_match", "interval_hit"]:
            if key not in hit_metrics:
                reasons.append(f"hit_metrics missing {key}")

    error_metrics = data.get("error_metrics")
    if isinstance(error_metrics, dict):
        for key in ["high_forecast_error", "low_forecast_error", "absolute_error"]:
            if key not in error_metrics:
                reasons.append(f"error_metrics missing {key}")

    return {
        "loaded": True,
        "required_keys_present": not missing_keys(data, REQUIRED_REVIEW_KEYS),
        "evaluation_metrics_present": all(isinstance(data.get(key), dict) for key in [
            "hit_metrics",
            "interval_coverage",
            "error_metrics",
        ]),
    }, reasons


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate daily report forecast roadmap files.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    reasons: list[str] = []

    missing_files = [rel_path for rel_path in REQUIRED_FILES if not (repo_root / rel_path).is_file()]
    for rel_path in missing_files:
        reasons.append(f"required file missing: {rel_path}")

    doc_text = ""
    doc_path = repo_root / DOC_PATH
    if doc_path.is_file():
        doc_text = doc_path.read_text(encoding="utf-8")
        for phrase in DOC_REQUIRED_PHRASES:
            if phrase not in doc_text:
                reasons.append(f"required doc phrase missing: {phrase}")
        for phrase in REQUIRED_SOURCE_PRIORITY_PHRASES:
            if phrase not in doc_text:
                reasons.append(f"required source priority phrase missing: {phrase}")
        reasons.extend(detect_secret_like_text(DOC_PATH, doc_text))

    contract_data: Any | None = None
    contract_error: str | None = None
    contract_path = repo_root / CONTRACT_PATH
    if contract_path.is_file():
        contract_data, contract_error = load_json(contract_path)
        if contract_error:
            reasons.append(f"invalid JSON in {CONTRACT_PATH}: {contract_error}")

    review_data: Any | None = None
    review_error: str | None = None
    review_path = repo_root / REVIEW_PATH
    if review_path.is_file():
        review_data, review_error = load_json(review_path)
        if review_error:
            reasons.append(f"invalid JSON in {REVIEW_PATH}: {review_error}")

    contract_summary: dict[str, Any] = {"loaded": False}
    if contract_error is None and contract_data is not None:
        contract_summary, contract_reasons = validate_contract(contract_data)
        reasons.extend(contract_reasons)
        for text in iter_strings(contract_data):
            reasons.extend(detect_secret_like_text(CONTRACT_PATH, text))

    review_summary: dict[str, Any] = {"loaded": False}
    if review_error is None and review_data is not None:
        review_summary, review_reasons = validate_review(review_data)
        reasons.extend(review_reasons)
        for text in iter_strings(review_data):
            reasons.extend(detect_secret_like_text(REVIEW_PATH, text))

    result = {
        "ok": True,
        "passed": not reasons,
        "required_files": REQUIRED_FILES,
        "missing_files": missing_files,
        "contract": contract_summary,
        "review_result": review_summary,
        "doc_checks": {
            "required_phrases_present": bool(doc_text) and not [
                phrase for phrase in DOC_REQUIRED_PHRASES if phrase not in doc_text
            ],
            "source_priority_present": bool(doc_text) and not [
                phrase for phrase in REQUIRED_SOURCE_PRIORITY_PHRASES if phrase not in doc_text
            ],
        },
        "side_effects": {
            "files_modified": False,
            "production_pipeline_changed": False,
            "notification_sent": False,
            "trading_execution_run": False,
            "order_execution_run": False,
            "runtime_queue_modified": False,
            "secrets_read": False,
        },
        "reasons": reasons,
    }

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
