#!/usr/bin/env python3
"""Build a deterministic Daily Report Dashboard Preview Feed V1 fixture."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_dashboard_preview_feed_input.example.json")
SCHEMA_VERSION = "daily_report_dashboard_preview_feed_v1"
SOURCE_SCHEMA_VERSION = "daily_report_preview_index_v1"
SIDE_EFFECTS = {
    "read_secrets": False,
    "called_external_model_runtime": False,
    "called_market_data_runtime": False,
    "sent_notification": False,
    "placed_trade_order": False,
    "modified_portfolio": False,
    "wrote_persistent_store": False,
    "modified_schedule_or_service": False,
    "modified_github_remote": False,
    "sent_daily_report": False,
    "wrote_production_db": False,
    "deployed_dashboard": False,
    "created_api_server": False,
}
SAFETY = {
    "repo_only": True,
    "fixture_only": True,
    "preview_only": True,
    "advisory_only": True,
    "requires_human_review": True,
    "dashboard_deploy": False,
    "api_server_created": False,
    "no_external_model_calls": True,
    "no_market_data_calls": True,
    "no_delivery_actions": True,
    "no_persistent_store_writes": True,
    "no_portfolio_actions": True,
    "no_schedule_service_changes": True,
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


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def resolve_repo_path(raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SystemExit("referenced fixture path must be a non-empty string")
    path = Path(raw_path)
    if path.is_absolute():
        raise SystemExit("referenced fixture path must be repo-relative")
    if ".." in path.parts:
        raise SystemExit("referenced fixture path must not contain parent traversal")
    return path


def stable_json(payload: Any, pretty: bool) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    return f"{text}\n" if pretty else text


def slug_date(value: Any) -> str:
    if isinstance(value, str) and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", value):
        return value.replace("-", "")
    return "unknown_date"


def warning_badges(warnings: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "badge_id": f"warning_{index + 1}",
            "label": str(warning),
            "severity": "warning",
        }
        for index, warning in enumerate(warnings)
    ]


def status_for_entry(entry: dict[str, Any]) -> str:
    if entry.get("requires_human_review") is True:
        return "requires_human_review"
    if as_list(entry.get("warnings")):
        return "warning"
    return "ready"


def build_card(entry: dict[str, Any]) -> dict[str, Any]:
    report_date = entry.get("report_date")
    preview_id = entry.get("preview_id")
    warnings = [str(item) for item in as_list(entry.get("warnings"))]
    status = status_for_entry(entry)
    sort_key = f"{report_date or 'unknown'}#{preview_id or 'unknown'}"
    return {
        "card_id": f"daily_report_preview_card_{slug_date(report_date)}",
        "preview_id": preview_id,
        "card_title": entry.get("title"),
        "report_date": report_date,
        "status": status,
        "warning_badges": warning_badges(warnings),
        "advisory_only_badge": {
            "enabled": entry.get("advisory_only") is True,
            "label": "Advisory only",
        },
        "preview_only_badge": {
            "enabled": entry.get("preview_only") is True,
            "label": "Preview only",
        },
        "requires_human_review_badge": {
            "enabled": entry.get("requires_human_review") is True,
            "label": "Requires human review",
        },
        "manifest_ref": entry.get("manifest_ref"),
        "markdown_ref": entry.get("markdown_ref"),
        "renderer_source_ref": entry.get("renderer_source_ref"),
        "section_count": entry.get("section_count"),
        "sort_key": sort_key,
        "filter_facets": {
            "report_date": report_date,
            "status": status,
            "has_warnings": bool(warnings),
            "advisory_only": entry.get("advisory_only") is True,
            "preview_only": entry.get("preview_only") is True,
            "requires_human_review": entry.get("requires_human_review") is True,
        },
    }


def unique_sorted(values: list[Any]) -> list[Any]:
    return sorted({value for value in values if value is not None})


def build_filters(cards: list[dict[str, Any]]) -> dict[str, Any]:
    facets = [as_dict(card.get("filter_facets")) for card in cards]
    return {
        "report_dates": unique_sorted([facet.get("report_date") for facet in facets]),
        "statuses": unique_sorted([facet.get("status") for facet in facets]),
        "has_warnings": unique_sorted([facet.get("has_warnings") for facet in facets]),
        "advisory_only": unique_sorted([facet.get("advisory_only") for facet in facets]),
        "preview_only": unique_sorted([facet.get("preview_only") for facet in facets]),
        "requires_human_review": unique_sorted(
            [facet.get("requires_human_review") for facet in facets]
        ),
    }


def source_preview_index_summary(source_path: Path, index_result: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(index_result.get("validation_summary"))
    preview_index = as_dict(index_result.get("preview_index"))
    preview_summary = as_dict(index_result.get("preview_summary"))
    return {
        "source_path": str(source_path),
        "source_schema_version": index_result.get("schema_version"),
        "source_task_id": index_result.get("task_id"),
        "source_run_id": index_result.get("run_id"),
        "source_generated_at": index_result.get("generated_at"),
        "source_mode": index_result.get("mode"),
        "source_decision": index_result.get("decision"),
        "source_ok": index_result.get("ok") is True,
        "source_index_id": preview_index.get("index_id"),
        "source_preview_count": preview_summary.get("preview_count"),
        "source_warning_count": preview_summary.get("warning_count"),
        "source_requires_human_review_count": preview_summary.get("requires_human_review_count"),
        "source_entry_count": validation.get("preview_entry_count"),
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source_path = resolve_repo_path(as_dict(data.get("input_sources")).get("preview_index_result_path"))
    index_result = load_json(source_path)
    config = as_dict(data.get("feed_config"))
    source_summary = source_preview_index_summary(source_path, index_result)
    entries = [entry for entry in as_list(index_result.get("preview_entries")) if isinstance(entry, dict)]
    cards = sorted((build_card(entry) for entry in entries), key=lambda card: str(card["sort_key"]), reverse=True)
    filters = build_filters(cards)
    warnings = sorted(
        {
            badge.get("label")
            for card in cards
            for badge in as_list(card.get("warning_badges"))
            if isinstance(badge, dict) and badge.get("label")
        }
    )
    validation_summary = {
        "source_schema_expected": SOURCE_SCHEMA_VERSION,
        "source_schema_matched": source_summary.get("source_schema_version") == SOURCE_SCHEMA_VERSION,
        "source_ok": source_summary.get("source_ok") is True,
        "source_mode_fixture_dry_run": source_summary.get("source_mode") == "fixture_dry_run",
        "dashboard_feed_included": True,
        "preview_cards_included": True,
        "preview_card_count": len(cards),
        "filters_included": True,
        "sort_included": True,
        "manifest_refs_present": all(bool(card.get("manifest_ref")) for card in cards),
        "markdown_refs_present": all(bool(card.get("markdown_ref")) for card in cards),
        "renderer_source_refs_present": all(bool(card.get("renderer_source_ref")) for card in cards),
        "deterministic_output": True,
        "fixture_only": True,
        "warnings": warnings,
    }
    dashboard_feed = {
        "feed_id": config.get("feed_id", "daily_report_dashboard_preview_feed"),
        "generated_at": data.get("generated_at"),
        "title": config.get("title", "Daily Report Dashboard Preview Feed"),
        "card_count": len(cards),
        "cards_ref": "embedded:preview_cards",
        "filters_ref": "embedded:filters",
        "source_preview_index_ref": str(source_path),
    }
    sort = {
        "default": "report_date_desc",
        "key": "sort_key",
        "direction": "desc",
        "stable_tiebreaker": "preview_id",
    }
    ok = (
        validation_summary["source_schema_matched"]
        and validation_summary["source_ok"]
        and validation_summary["source_mode_fixture_dry_run"]
        and validation_summary["preview_card_count"] > 0
        and validation_summary["manifest_refs_present"]
        and validation_summary["markdown_refs_present"]
        and validation_summary["renderer_source_refs_present"]
        and all(value is False for value in SIDE_EFFECTS.values())
        and all(value is True for key, value in SAFETY.items() if key.startswith("no_") or key.endswith("_only"))
        and SAFETY["repo_only"] is True
        and SAFETY["fixture_only"] is True
        and SAFETY["dashboard_deploy"] is False
        and SAFETY["api_server_created"] is False
    )
    decision = (
        "daily_report_dashboard_preview_feed_completed_with_warnings"
        if warnings
        else "daily_report_dashboard_preview_feed_completed"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-087"),
        "run_id": data.get("run_id", "daily-report-dashboard-preview-feed-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "dashboard_feed": dashboard_feed,
        "preview_cards": cards,
        "filters": filters,
        "sort": sort,
        "source_preview_index_summary": source_summary,
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision if ok else "validation_failed",
        "next_recommendation": "Use this deterministic feed as a private dashboard fixture after human review; do not deploy or deliver from it directly.",
    }


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Daily Report Dashboard Preview Feed V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--cards-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["preview_cards"], Path(args.cards_output), args.pretty)
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
