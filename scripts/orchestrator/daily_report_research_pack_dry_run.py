#!/usr/bin/env python3
"""Build a deterministic Daily Report Research Pack V1 fixture."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_research_pack_input.example.json")
SCHEMA_VERSION = "daily_report_research_pack_v1"
FORECAST_SCHEMA_VERSION = "daily_report_forecast_review_section_v1"
INTELLIGENCE_SCHEMA_VERSION = "daily_report_intelligence_integration_v1"
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
    "rendered_runtime_report": False,
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
    return path


def source_paths(data: dict[str, Any]) -> tuple[Path, Path]:
    sources = as_dict(data.get("input_sources"))
    return (
        resolve_repo_path(sources.get("forecast_review_section_result_path")),
        resolve_repo_path(sources.get("intelligence_integration_result_path")),
    )


def section_summary(section: dict[str, Any]) -> dict[str, Any]:
    return {
        "section_id": section.get("section_id"),
        "section_type": section.get("section_type"),
        "title": section.get("title"),
        "placement": section.get("placement"),
        "priority": section.get("priority"),
        "render_mode": section.get("render_mode"),
        "source_refs": deepcopy(section.get("source_refs", [])),
        "advisory_only": section.get("advisory_only") is True,
        "requires_human_review": section.get("requires_human_review") is True,
    }


def forecast_summary(forecast_result: dict[str, Any]) -> dict[str, Any]:
    section = as_dict(forecast_result.get("daily_report_section"))
    machine = as_dict(section.get("machine_readable"))
    source_summary = as_dict(forecast_result.get("source_summary"))
    return {
        "source_schema_version": forecast_result.get("schema_version"),
        "source_task_id": forecast_result.get("task_id"),
        "source_run_id": forecast_result.get("run_id"),
        "source_decision": forecast_result.get("decision"),
        "source_ok": forecast_result.get("ok") is True,
        "section": section_summary(section),
        "quality_status": machine.get("quality_status"),
        "insufficient_data": machine.get("insufficient_data") is True,
        "source_section_count": source_summary.get("source_section_count"),
        "source_refs": deepcopy(section.get("source_refs", [])),
        "advisory_only": True,
        "requires_human_review": True,
    }


def intelligence_summary(intelligence_result: dict[str, Any]) -> dict[str, Any]:
    section = as_dict(intelligence_result.get("daily_report_intelligence_section"))
    credibility = as_dict(intelligence_result.get("source_credibility_summary"))
    return {
        "source_schema_version": intelligence_result.get("schema_version"),
        "source_task_id": intelligence_result.get("task_id"),
        "source_run_id": intelligence_result.get("run_id"),
        "source_decision": intelligence_result.get("decision"),
        "source_ok": intelligence_result.get("ok") is True,
        "section": section_summary(section),
        "company_topic_count": as_dict(intelligence_result.get("company_intelligence_summary")).get("topic_count"),
        "industry_topic_count": as_dict(intelligence_result.get("industry_peer_context_summary")).get("industry_topic_count"),
        "combined_source_count": credibility.get("combined_source_count"),
        "source_refs": deepcopy(section.get("source_refs", [])),
        "advisory_only": True,
        "requires_human_review": True,
    }


def source_credibility_summary(intelligence_result: dict[str, Any]) -> dict[str, Any]:
    credibility = as_dict(intelligence_result.get("source_credibility_summary"))
    return {
        "source": "daily_report_intelligence_integration_result.source_credibility_summary",
        "metadata_preserved": credibility.get("metadata_preserved") is True,
        "company_source_count": credibility.get("company_source_count"),
        "industry_peer_source_count": credibility.get("industry_peer_source_count"),
        "combined_source_count": credibility.get("combined_source_count"),
        "average_credibility_score": credibility.get("average_credibility_score"),
        "low_credibility_source_ids": deepcopy(credibility.get("low_credibility_source_ids", [])),
        "review_required_source_ids": deepcopy(credibility.get("review_required_source_ids", [])),
        "core_scoring_allowed_source_ids": deepcopy(credibility.get("core_scoring_allowed_source_ids", [])),
        "source_credibility_scores": deepcopy(credibility.get("source_credibility_scores", [])),
        "advisory_only": True,
        "requires_human_review": True,
    }


def ordered_sections(data: dict[str, Any], forecast_section: dict[str, Any], intelligence_section: dict[str, Any]) -> list[dict[str, Any]]:
    config = as_dict(data.get("research_pack_config"))
    requested_order = [str(item) for item in as_list(config.get("section_order"))]
    by_id = {
        str(forecast_section.get("section_id", "forecast_review")): forecast_section,
        str(intelligence_section.get("section_id", "daily_report_intelligence")): intelligence_section,
    }
    if not requested_order:
        requested_order = ["forecast_review", "daily_report_intelligence"]
    result: list[dict[str, Any]] = []
    for section_id in requested_order:
        if section_id in by_id:
            result.append(deepcopy(by_id[section_id]))
    for section_id in sorted(by_id):
        if section_id not in requested_order:
            result.append(deepcopy(by_id[section_id]))
    return result


def build_markdown(title: str, sections: list[dict[str, Any]], risk_and_limitations: list[str]) -> str:
    lines = [
        f"# {title}",
        "",
        "> Repo-only, fixture-only research pack. Advisory only; human review is required before any daily report use.",
        "",
    ]
    for section in sections:
        markdown = str(section.get("markdown", "")).strip()
        if markdown:
            lines.extend([markdown, ""])
    lines.append("## Research Pack Risk And Limitations")
    for item in risk_and_limitations:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "_No external model call, market data call, delivery action, persistent store write, portfolio action, or schedule/service change was performed._",
    ])
    return "\n".join(lines)


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    forecast_path, intelligence_path = source_paths(data)
    forecast_result = load_json(forecast_path)
    intelligence_result = load_json(intelligence_path)
    forecast_section = as_dict(forecast_result.get("daily_report_section"))
    intelligence_section = as_dict(intelligence_result.get("daily_report_intelligence_section"))
    sections = ordered_sections(data, forecast_section, intelligence_section)
    section_order = [str(section.get("section_id")) for section in sections]
    config = as_dict(data.get("research_pack_config"))
    title = str(config.get("title", "Daily Report Research Pack"))
    risk_and_limitations = [
        "This research pack is assembled from static repo fixtures only.",
        "Forecast review metrics may be insufficient and must not be over-interpreted.",
        "Source credibility metadata is preserved from the intelligence integration fixture and is not recalculated here.",
        "This output is advisory only and must not be treated as investment advice or an instruction to trade.",
        "No live data, external model runtime, delivery channel, persistent store, portfolio, schedule, or service integration is authorized.",
    ]
    markdown = build_markdown(title, sections, risk_and_limitations)
    warnings = []
    if forecast_result.get("schema_version") != FORECAST_SCHEMA_VERSION:
        warnings.append("forecast review source schema mismatch")
    if intelligence_result.get("schema_version") != INTELLIGENCE_SCHEMA_VERSION:
        warnings.append("intelligence source schema mismatch")
    if forecast_result.get("decision") == "forecast_review_section_completed_with_insufficient_data":
        warnings.append("forecast review source reports insufficient data")
    if as_dict(intelligence_result.get("source_credibility_summary")).get("review_required_source_ids"):
        warnings.append("human review required for one or more intelligence sources")
    ok = (
        forecast_result.get("ok") is True
        and intelligence_result.get("ok") is True
        and forecast_result.get("schema_version") == FORECAST_SCHEMA_VERSION
        and intelligence_result.get("schema_version") == INTELLIGENCE_SCHEMA_VERSION
        and len(sections) == 2
    )
    decision = "daily_report_research_pack_completed_with_warnings" if warnings else "daily_report_research_pack_completed"
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-083"),
        "run_id": data.get("run_id", "daily-report-research-pack-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "source_summary": {
            "forecast_review_source_schema_version": forecast_result.get("schema_version"),
            "intelligence_source_schema_version": intelligence_result.get("schema_version"),
            "forecast_review_source_run_id": forecast_result.get("run_id"),
            "intelligence_source_run_id": intelligence_result.get("run_id"),
            "forecast_review_source_decision": forecast_result.get("decision"),
            "intelligence_source_decision": intelligence_result.get("decision"),
            "forecast_review_source_ok": forecast_result.get("ok") is True,
            "intelligence_source_ok": intelligence_result.get("ok") is True,
            "source_paths": {
                "forecast_review_section_result_path": str(forecast_path),
                "intelligence_integration_result_path": str(intelligence_path),
            },
        },
        "research_pack": {
            "pack_id": config.get("pack_id", "daily_report_research_pack"),
            "title": title,
            "intended_report_slot": config.get("intended_report_slot", "future_0700_daily_report_research_payload"),
            "render_mode": "static_markdown_with_machine_readable_payload",
            "markdown": markdown,
            "machine_readable": {
                "section_order": section_order,
                "sections": [section_summary(section) for section in sections],
                "forecast_review_summary": forecast_summary(forecast_result),
                "intelligence_summary": intelligence_summary(intelligence_result),
                "source_credibility_summary": source_credibility_summary(intelligence_result),
                "advisory_only": True,
                "requires_human_review": True,
            },
            "source_refs": [
                "input_sources.forecast_review_section_result_path",
                "input_sources.intelligence_integration_result_path",
            ],
            "advisory_only": True,
            "requires_human_review": True,
        },
        "sections": sections,
        "section_order": section_order,
        "forecast_review_summary": forecast_summary(forecast_result),
        "intelligence_summary": intelligence_summary(intelligence_result),
        "source_credibility_summary": source_credibility_summary(intelligence_result),
        "risk_and_limitations": risk_and_limitations,
        "validation_summary": {
            "forecast_schema_expected": FORECAST_SCHEMA_VERSION,
            "intelligence_schema_expected": INTELLIGENCE_SCHEMA_VERSION,
            "forecast_schema_matched": forecast_result.get("schema_version") == FORECAST_SCHEMA_VERSION,
            "intelligence_schema_matched": intelligence_result.get("schema_version") == INTELLIGENCE_SCHEMA_VERSION,
            "section_count": len(sections),
            "section_order_preserved": section_order == as_list(config.get("section_order", section_order)),
            "placement_metadata_preserved": all(section.get("placement") for section in sections),
            "source_refs_preserved": all(isinstance(section.get("source_refs"), list) and section.get("source_refs") for section in sections),
            "source_credibility_metadata_preserved": as_dict(intelligence_result.get("source_credibility_summary")).get("metadata_preserved") is True,
            "markdown_included": bool(markdown),
            "machine_readable_included": True,
            "deterministic_output": True,
            "fixture_only": True,
            "warnings": warnings,
        },
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": {
            "repo_only": True,
            "fixture_only": True,
            "advisory_only": True,
            "requires_human_review": True,
            "no_external_model_calls": True,
            "no_market_data_calls": True,
            "no_delivery_actions": True,
            "no_persistent_store_writes": True,
            "no_portfolio_actions": True,
            "no_schedule_service_changes": True,
        },
        "ok": ok,
        "decision": decision if ok else "validation_failed",
        "next_recommendation": "Review this static research pack contract before wiring it into any 07:00 daily report renderer.",
    }


def write_text(text: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def write_json(payload: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if pretty:
        rendered += "\n"
    write_text(rendered, output)
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Daily Report Research Pack V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--markdown-output")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    if args.markdown_output:
        write_text(str(result["research_pack"]["markdown"]) + "\n", Path(args.markdown_output))
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
