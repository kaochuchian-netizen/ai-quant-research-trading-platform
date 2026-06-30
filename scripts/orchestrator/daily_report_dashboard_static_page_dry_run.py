#!/usr/bin/env python3
"""Build a deterministic Daily Report Dashboard Static Page V1 fixture."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_dashboard_static_page_input.example.json")
SCHEMA_VERSION = "daily_report_dashboard_static_page_v1"
SOURCE_SCHEMA_VERSION = "daily_report_dashboard_preview_feed_v1"
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


def badge_group(cards: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    badges: list[dict[str, Any]] = []
    for card in cards:
        badge = as_dict(card.get(key))
        if badge.get("enabled") is True:
            badges.append(
                {
                    "badge_id": f"{key}_{card.get('card_id')}",
                    "card_id": card.get("card_id"),
                    "label": badge.get("label"),
                    "severity": "info" if key != "requires_human_review_badge" else "warning",
                }
            )
    return badges


def warning_badges(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    badges: list[dict[str, Any]] = []
    for card in cards:
        for badge in as_list(card.get("warning_badges")):
            if not isinstance(badge, dict):
                continue
            badges.append(
                {
                    "badge_id": f"{card.get('card_id')}_{badge.get('badge_id')}",
                    "card_id": card.get("card_id"),
                    "label": badge.get("label"),
                    "severity": badge.get("severity", "warning"),
                }
            )
    return badges


def overview_metrics(cards: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [as_dict(card.get("filter_facets")).get("status") or card.get("status") for card in cards]
    return {
        "preview_card_count": len(cards),
        "warning_badge_count": len(warnings),
        "advisory_only_count": sum(1 for card in cards if as_dict(card.get("advisory_only_badge")).get("enabled") is True),
        "preview_only_count": sum(1 for card in cards if as_dict(card.get("preview_only_badge")).get("enabled") is True),
        "requires_human_review_count": sum(
            1 for card in cards if as_dict(card.get("requires_human_review_badge")).get("enabled") is True
        ),
        "ready_count": statuses.count("ready"),
        "warning_count": statuses.count("warning"),
        "status_counts": {status: statuses.count(status) for status in sorted({str(status) for status in statuses})},
    }


def drilldown_placeholders(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "placeholder_id": f"drilldown_{card.get('card_id')}",
            "card_id": card.get("card_id"),
            "preview_id": card.get("preview_id"),
            "title": f"Drill-down placeholder for {card.get('card_title')}",
            "status": "placeholder_only",
            "enabled": False,
            "reason": "Static contract fixture only; private dashboard drill-down rendering is not implemented in V1.",
            "manifest_ref": card.get("manifest_ref"),
            "markdown_ref": card.get("markdown_ref"),
            "renderer_source_ref": card.get("renderer_source_ref"),
        }
        for card in cards
    ]


def source_feed_summary(source_path: Path, feed_result: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(feed_result.get("validation_summary"))
    dashboard_feed = as_dict(feed_result.get("dashboard_feed"))
    return {
        "source_path": str(source_path),
        "source_schema_version": feed_result.get("schema_version"),
        "source_task_id": feed_result.get("task_id"),
        "source_run_id": feed_result.get("run_id"),
        "source_generated_at": feed_result.get("generated_at"),
        "source_mode": feed_result.get("mode"),
        "source_decision": feed_result.get("decision"),
        "source_ok": feed_result.get("ok") is True,
        "source_feed_id": dashboard_feed.get("feed_id"),
        "source_card_count": dashboard_feed.get("card_count"),
        "source_preview_card_count": validation.get("preview_card_count"),
        "source_warning_count": len(as_list(validation.get("warnings"))),
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source_path = resolve_repo_path(as_dict(data.get("input_sources")).get("dashboard_preview_feed_result_path"))
    feed_result = load_json(source_path)
    config = as_dict(data.get("page_config"))
    cards = [deepcopy(card) for card in as_list(feed_result.get("preview_cards")) if isinstance(card, dict)]
    cards = sorted(cards, key=lambda card: str(card.get("sort_key", "")), reverse=True)
    latest_card = deepcopy(cards[0]) if cards else None
    warnings = warning_badges(cards)
    advisory_badges = badge_group(cards, "advisory_only_badge")
    preview_badges = badge_group(cards, "preview_only_badge")
    review_badges = badge_group(cards, "requires_human_review_badge")
    source_summary = source_feed_summary(source_path, feed_result)
    page = {
        "page_id": config.get("page_id", "daily_report_dashboard_static_page"),
        "page_title": config.get("page_title", "Daily Report Dashboard Static Page"),
        "generated_at": data.get("generated_at"),
        "latest_preview_card_ref": latest_card.get("card_id") if isinstance(latest_card, dict) else None,
        "preview_cards_ref": "embedded:preview_cards",
        "overview_metrics_ref": "embedded:overview_metrics",
        "filter_facets_ref": "embedded:filter_facets",
        "sort_options_ref": "embedded:sort_options",
        "warning_badges_ref": "embedded:warning_badges",
        "drilldown_placeholders_ref": "embedded:drilldown_placeholders",
        "manifest_ref": latest_card.get("manifest_ref") if isinstance(latest_card, dict) else None,
        "markdown_ref": latest_card.get("markdown_ref") if isinstance(latest_card, dict) else None,
        "renderer_source_ref": latest_card.get("renderer_source_ref") if isinstance(latest_card, dict) else None,
    }
    filter_facets = deepcopy(feed_result.get("filters", {}))
    sort_options = [
        deepcopy(feed_result.get("sort", {})),
        {
            "default": "status_then_report_date_desc",
            "key": "status_sort_key",
            "direction": "asc",
            "stable_tiebreaker": "preview_id",
        },
    ]
    metrics = overview_metrics(cards, warnings)
    validation_summary = {
        "source_schema_expected": SOURCE_SCHEMA_VERSION,
        "source_schema_matched": source_summary.get("source_schema_version") == SOURCE_SCHEMA_VERSION,
        "source_ok": source_summary.get("source_ok") is True,
        "source_mode_fixture_dry_run": source_summary.get("source_mode") == "fixture_dry_run",
        "dashboard_page_included": True,
        "latest_preview_card_included": latest_card is not None,
        "preview_cards_included": bool(cards),
        "preview_card_count": len(cards),
        "overview_metrics_included": True,
        "filter_facets_included": isinstance(filter_facets, dict),
        "sort_options_included": True,
        "warning_badges_included": True,
        "drilldown_placeholders_included": True,
        "manifest_ref_present": bool(page.get("manifest_ref")),
        "markdown_ref_present": bool(page.get("markdown_ref")),
        "renderer_source_ref_present": bool(page.get("renderer_source_ref")),
        "deterministic_output": True,
        "fixture_only": True,
        "warnings": sorted({str(badge.get("label")) for badge in warnings if badge.get("label")}),
    }
    ok = (
        validation_summary["source_schema_matched"]
        and validation_summary["source_ok"]
        and validation_summary["source_mode_fixture_dry_run"]
        and validation_summary["latest_preview_card_included"]
        and validation_summary["manifest_ref_present"]
        and validation_summary["markdown_ref_present"]
        and validation_summary["renderer_source_ref_present"]
        and all(value is False for value in SIDE_EFFECTS.values())
        and SAFETY["repo_only"] is True
        and SAFETY["fixture_only"] is True
        and SAFETY["dashboard_deploy"] is False
        and SAFETY["api_server_created"] is False
    )
    decision = (
        "daily_report_dashboard_static_page_completed_with_warnings"
        if validation_summary["warnings"]
        else "daily_report_dashboard_static_page_completed"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-088"),
        "run_id": data.get("run_id", "daily-report-dashboard-static-page-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "dashboard_page": page,
        "latest_preview_card": latest_card,
        "preview_cards": cards,
        "overview_metrics": metrics,
        "filter_facets": filter_facets,
        "sort_options": sort_options,
        "warning_badges": warnings,
        "advisory_only_badges": advisory_badges,
        "preview_only_badges": preview_badges,
        "requires_human_review_badges": review_badges,
        "drilldown_placeholders": drilldown_placeholders(cards),
        "source_dashboard_preview_feed_summary": source_summary,
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision if ok else "validation_failed",
        "next_recommendation": "Use this deterministic static page fixture for private dashboard rendering after human review; do not deploy, serve, or deliver it directly.",
    }


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "daily_report_dashboard_static_page_summary_v1",
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "page_id": as_dict(result.get("dashboard_page")).get("page_id"),
        "page_title": as_dict(result.get("dashboard_page")).get("page_title"),
        "latest_preview_card_id": as_dict(result.get("latest_preview_card")).get("card_id"),
        "overview_metrics": deepcopy(result.get("overview_metrics")),
        "warning_badge_count": len(as_list(result.get("warning_badges"))),
        "drilldown_placeholder_count": len(as_list(result.get("drilldown_placeholders"))),
        "source_run_id": as_dict(result.get("source_dashboard_preview_feed_summary")).get("source_run_id"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "deterministic_output": as_dict(result.get("validation_summary")).get("deterministic_output"),
        "side_effects": deepcopy(result.get("side_effects")),
        "safety": deepcopy(result.get("safety")),
    }


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Daily Report Dashboard Static Page V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(build_summary(result), Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
