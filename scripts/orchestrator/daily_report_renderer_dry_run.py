#!/usr/bin/env python3
"""Build a deterministic Daily Report Renderer Contract V1 fixture."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_renderer_input.example.json")
SCHEMA_VERSION = "daily_report_renderer_contract_v1"
RESEARCH_PACK_SCHEMA_VERSION = "daily_report_research_pack_v1"
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


def section_metadata(section: dict[str, Any], placement: str) -> dict[str, Any]:
    return {
        "section_id": section.get("section_id"),
        "title": section.get("title"),
        "placement": placement,
        "priority": section.get("priority"),
        "source_refs": deepcopy(section.get("source_refs", [])),
        "advisory_only": section.get("advisory_only") is True,
        "requires_human_review": section.get("requires_human_review") is True,
    }


def report_section(section: dict[str, Any], placement: str) -> dict[str, Any]:
    metadata = section_metadata(section, placement)
    return {
        **metadata,
        "source_section_id": section.get("section_id"),
        "source_placement": section.get("placement"),
        "render_mode": "static_markdown_with_machine_readable_payload",
        "markdown": str(section.get("markdown", "")).strip(),
        "machine_readable": deepcopy(section.get("machine_readable", {})),
        "badges": deepcopy(section.get("badges", [])),
    }


def ordered_report_sections(data: dict[str, Any], research_pack: dict[str, Any]) -> list[dict[str, Any]]:
    config = as_dict(data.get("renderer_config"))
    requested_order = [str(item) for item in as_list(config.get("section_order"))]
    source_sections = [section for section in as_list(research_pack.get("sections")) if isinstance(section, dict)]
    by_id = {str(section.get("section_id")): section for section in source_sections if section.get("section_id")}
    if not requested_order:
        requested_order = [str(item) for item in as_list(research_pack.get("section_order"))]
    if not requested_order:
        requested_order = sorted(by_id)

    result: list[dict[str, Any]] = []
    for index, section_id in enumerate(requested_order, start=1):
        if section_id in by_id:
            result.append(report_section(by_id[section_id], f"body_{index:02d}"))
    for section_id in sorted(by_id):
        if section_id not in requested_order:
            result.append(report_section(by_id[section_id], f"body_{len(result) + 1:02d}"))
    return result


def source_credibility_summary(research_pack: dict[str, Any]) -> dict[str, Any]:
    credibility = as_dict(research_pack.get("source_credibility_summary"))
    return {
        "source": "daily_report_research_pack_result.source_credibility_summary",
        "metadata_preserved": credibility.get("metadata_preserved") is True,
        "combined_source_count": credibility.get("combined_source_count"),
        "average_credibility_score": credibility.get("average_credibility_score"),
        "low_credibility_source_ids": deepcopy(credibility.get("low_credibility_source_ids", [])),
        "review_required_source_ids": deepcopy(credibility.get("review_required_source_ids", [])),
        "core_scoring_allowed_source_ids": deepcopy(credibility.get("core_scoring_allowed_source_ids", [])),
        "source_credibility_scores": deepcopy(credibility.get("source_credibility_scores", [])),
        "advisory_only": True,
        "requires_human_review": True,
    }


def build_markdown(
    title: str,
    report_date: str,
    report_sections: list[dict[str, Any]],
    risk_and_limitations: list[str],
    warnings: list[str],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- Report date: `{report_date}`",
        "- Mode: `fixture_dry_run`",
        "- Advisory only: `true`",
        "- Requires human review: `true`",
        "",
        "> Repo-only, fixture-only daily report renderer output. This is not a delivery payload and must be reviewed by a human before any future 07:00 report use.",
        "",
    ]
    if warnings:
        lines.append("## Human Review Warnings")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    for section in report_sections:
        markdown = str(section.get("markdown", "")).strip()
        if markdown:
            lines.extend([markdown, ""])

    lines.append("## Risk And Limitations")
    for item in risk_and_limitations:
        lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "_No external model call, market data call, delivery action, persistent store write, portfolio action, schedule/service change, or production report send was performed._",
        ]
    )
    return "\n".join(lines)


def validation_warnings(research_pack: dict[str, Any], report_sections: list[dict[str, Any]]) -> list[str]:
    warnings = [str(item) for item in as_list(as_dict(research_pack.get("validation_summary")).get("warnings"))]
    if research_pack.get("decision") == "daily_report_research_pack_completed_with_warnings":
        warnings.append("source research pack completed with warnings")
    if as_dict(research_pack.get("forecast_review_summary")).get("insufficient_data") is True:
        warnings.append("forecast review source reports insufficient data")
    if as_dict(research_pack.get("source_credibility_summary")).get("review_required_source_ids"):
        warnings.append("one or more source credibility records require human review")
    if any(not section.get("markdown") for section in report_sections):
        warnings.append("one or more report sections have empty markdown")
    return sorted(set(warnings))


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source_path = resolve_repo_path(as_dict(data.get("input_sources")).get("research_pack_result_path"))
    research_pack = load_json(source_path)
    config = as_dict(data.get("renderer_config"))
    report_date = str(config.get("report_date", "2026-06-30"))
    report_title = str(config.get("report_title", f"Daily Report {report_date}"))
    report_sections = ordered_report_sections(data, research_pack)
    section_order = [str(section.get("section_id")) for section in report_sections]
    warnings = validation_warnings(research_pack, report_sections)
    risk_and_limitations = [
        "This renderer output is assembled from static repo fixtures only.",
        "The source research pack is advisory-only and requires human review.",
        "Source refs, credibility metadata, and limitation notes are preserved from the source research pack.",
        "Forecast review content may be based on insufficient sample size and must not be over-interpreted.",
        "This output is not investment advice and does not authorize trading, portfolio, delivery, schedule, service, model, or data actions.",
    ]
    markdown = build_markdown(report_title, report_date, report_sections, risk_and_limitations, warnings)
    research_safety = as_dict(research_pack.get("safety"))
    ok = (
        research_pack.get("ok") is True
        and research_pack.get("schema_version") == RESEARCH_PACK_SCHEMA_VERSION
        and len(report_sections) >= 1
        and all(section.get("advisory_only") is True for section in report_sections)
        and all(section.get("requires_human_review") is True for section in report_sections)
    )
    decision = "daily_report_renderer_completed_with_warnings" if warnings else "daily_report_renderer_completed"
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-084"),
        "run_id": data.get("run_id", "daily-report-renderer-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "source_summary": {
            "source_schema_version": research_pack.get("schema_version"),
            "source_task_id": research_pack.get("task_id"),
            "source_run_id": research_pack.get("run_id"),
            "source_decision": research_pack.get("decision"),
            "source_ok": research_pack.get("ok") is True,
            "source_path": str(source_path),
            "source_section_order": deepcopy(research_pack.get("section_order", [])),
            "source_warning_count": len(as_list(as_dict(research_pack.get("validation_summary")).get("warnings"))),
            "source_credibility_metadata_preserved": as_dict(research_pack.get("source_credibility_summary")).get("metadata_preserved") is True,
        },
        "render_payload": {
            "payload_id": config.get("payload_id", "daily_report_render_payload"),
            "render_mode": "static_markdown_with_machine_readable_payload",
            "intended_report_slot": config.get("intended_report_slot", "future_0700_daily_report_delivery"),
            "report_title": report_title,
            "report_date": report_date,
            "section_order": section_order,
            "sections": [section_metadata(section, str(section.get("placement"))) for section in report_sections],
            "source_credibility_summary": source_credibility_summary(research_pack),
            "source_refs": ["input_sources.research_pack_result_path"],
            "advisory_only": True,
            "requires_human_review": True,
        },
        "report_title": report_title,
        "report_date": report_date,
        "report_sections": report_sections,
        "markdown": markdown,
        "section_order": section_order,
        "risk_and_limitations": risk_and_limitations,
        "validation_summary": {
            "source_schema_expected": RESEARCH_PACK_SCHEMA_VERSION,
            "source_schema_matched": research_pack.get("schema_version") == RESEARCH_PACK_SCHEMA_VERSION,
            "source_ok": research_pack.get("ok") is True,
            "section_count": len(report_sections),
            "section_order_preserved": section_order == as_list(research_pack.get("section_order")),
            "section_metadata_included": all(
                all(key in section for key in ["section_id", "title", "placement", "priority", "source_refs", "advisory_only", "requires_human_review"])
                for section in report_sections
            ),
            "source_refs_preserved": all(isinstance(section.get("source_refs"), list) and section.get("source_refs") for section in report_sections),
            "source_credibility_metadata_preserved": as_dict(research_pack.get("source_credibility_summary")).get("metadata_preserved") is True,
            "risk_and_limitations_preserved": bool(research_pack.get("risk_and_limitations")) and bool(risk_and_limitations),
            "markdown_included": bool(markdown),
            "machine_readable_render_payload_included": True,
            "deterministic_output": True,
            "fixture_only": True,
            "warnings": warnings,
        },
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": {
            "repo_only": research_safety.get("repo_only") is True,
            "fixture_only": research_safety.get("fixture_only") is True,
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
        "next_recommendation": "Review this static renderer payload before connecting any future 07:00 delivery workflow.",
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
    parser = argparse.ArgumentParser(description="Build Daily Report Renderer Contract V1 fixture.")
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
        write_text(str(result["markdown"]) + "\n", Path(args.markdown_output))
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
