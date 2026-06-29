#!/usr/bin/env python3
"""Build a deterministic Daily Report Forecast Review Section V1 fixture."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_forecast_review_section_input.example.json")
SCHEMA_VERSION = "daily_report_forecast_review_section_v1"
SOURCE_SCHEMA_VERSION = "dashboard_prediction_review_report_export_v1"
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
    "modified_github_remote": False,
    "modified_forecast_runtime_weights": False,
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


def source_export(data: dict[str, Any]) -> dict[str, Any]:
    value = data.get("source_report_export")
    return value if isinstance(value, dict) else {}


def source_report_payload(src: dict[str, Any]) -> dict[str, Any]:
    value = src.get("report_payload")
    return value if isinstance(value, dict) else {}


def source_sections(src: dict[str, Any]) -> list[dict[str, Any]]:
    report = source_report_payload(src)
    sections = report.get("sections")
    if not isinstance(sections, list):
        return []
    return [section for section in sections if isinstance(section, dict)]


def config(data: dict[str, Any]) -> dict[str, Any]:
    value = data.get("daily_report_section_config")
    return value if isinstance(value, dict) else {}


def has_insufficient_data(src: dict[str, Any]) -> bool:
    summary = src.get("export_summary")
    if isinstance(summary, dict) and summary.get("source_quality_status") == "insufficient_data":
        return True
    return "資料不足，不應過度解讀命中率" in json.dumps(src, ensure_ascii=False)


def section_by_id(sections: list[dict[str, Any]], section_id: str) -> dict[str, Any]:
    for section in sections:
        if section.get("section_id") == section_id:
            return section
    return {}


def bullet_from_section(section: dict[str, Any]) -> str:
    title = str(section.get("title", section.get("section_id", "Section")))
    markdown = str(section.get("markdown", "")).strip()
    return f"- **{title}**: {markdown}" if markdown else f"- **{title}**: n/a"


def build_markdown(
    section_title: str,
    sections: list[dict[str, Any]],
    insufficient: bool,
) -> str:
    ordered_ids = [
        "executive_summary",
        "forecast_quality_summary",
        "horizon_review_summary",
        "confidence_calibration_summary",
        "error_pattern_summary",
        "daily_improvement_recommendations",
        "risk_and_limitations",
        "next_steps",
    ]
    lines = [f"## {section_title}", ""]
    if insufficient:
        lines.extend(["> 資料不足，不應過度解讀命中率。", ""])
    for section_id in ordered_ids:
        section = section_by_id(sections, section_id)
        if section:
            lines.append(bullet_from_section(section))
    lines.extend([
        "",
        "_Fixture-only, advisory-only. Human review is required before any forecast tuning or report delivery._",
    ])
    return "\n".join(lines)


def machine_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for section in sections:
        result.append({
            "source_section_id": section.get("section_id"),
            "title": section.get("title"),
            "priority": section.get("priority"),
            "machine_readable": deepcopy(section.get("machine_readable", {})),
            "source_refs": deepcopy(section.get("source_refs", [])),
            "advisory_only": section.get("advisory_only") is True,
        })
    return result


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    src = source_export(data)
    sections = source_sections(src)
    section_config = config(data)
    section_id = section_config.get("section_id", "forecast_review")
    section_title = section_config.get("title", "Forecast Review")
    insufficient = has_insufficient_data(src)
    markdown = build_markdown(str(section_title), sections, insufficient)
    export_summary = src.get("export_summary") if isinstance(src.get("export_summary"), dict) else {}
    result_sections = machine_sections(sections)
    decision = (
        "forecast_review_section_completed_with_insufficient_data"
        if insufficient
        else "forecast_review_section_completed"
    )
    if not sections:
        decision = "no_report_sections"
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-075"),
        "run_id": data.get("run_id", "daily-report-forecast-review-section-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "source_summary": {
            "source_schema_version": src.get("schema_version"),
            "source_task_id": src.get("task_id"),
            "source_run_id": src.get("run_id"),
            "source_decision": src.get("decision"),
            "source_report_version": source_report_payload(src).get("report_version"),
            "source_section_count": len(sections),
            "source_quality_status": export_summary.get("source_quality_status"),
        },
        "daily_report_section": {
            "section_id": section_id,
            "section_type": "forecast_review",
            "title": section_title,
            "placement": section_config.get("placement", "after_forecast_summary"),
            "priority": section_config.get("priority", "high"),
            "render_mode": "static_markdown_with_machine_readable_payload",
            "markdown": markdown,
            "machine_readable": {
                "source_schema_version": src.get("schema_version"),
                "source_report_version": source_report_payload(src).get("report_version"),
                "source_sections": result_sections,
                "quality_status": export_summary.get("source_quality_status"),
                "insufficient_data": insufficient,
                "advisory_only": True,
                "requires_human_review": True,
            },
            "badges": {
                "fixture_only": True,
                "advisory_only": True,
                "insufficient_data": insufficient,
                "requires_human_review": True,
            },
            "source_refs": ["source_report_export.report_payload.sections"],
            "advisory_only": True,
            "requires_human_review": True,
        },
        "validation_summary": {
            "source_schema_expected": SOURCE_SCHEMA_VERSION,
            "source_schema_matched": src.get("schema_version") == SOURCE_SCHEMA_VERSION,
            "section_count": len(result_sections),
            "markdown_included": bool(markdown),
            "machine_readable_included": True,
            "static_report_section_ready": bool(sections),
        },
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": {
            "fixture_only": True,
            "repo_only": True,
            "advisory_only": True,
            "requires_human_review": True,
            "no_trading": True,
            "no_notification": True,
            "no_production_db_write": True,
            "no_runtime_weight_change": True,
            "static_report_contract_only": True,
        },
        "ok": bool(sections),
        "decision": decision,
        "next_recommendation": "Review section contract before enabling any runtime daily report delivery.",
    }


def write_result(result: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(result, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if pretty:
        rendered += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Daily Report Forecast Review Section V1 fixture.")
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
