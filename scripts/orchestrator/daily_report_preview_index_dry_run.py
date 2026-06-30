#!/usr/bin/env python3
"""Build a deterministic Daily Report Preview Index V1 fixture."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_preview_index_input.example.json")
SCHEMA_VERSION = "daily_report_preview_index_v1"
SOURCE_SCHEMA_VERSION = "daily_report_static_preview_export_v1"
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
}
SAFETY = {
    "repo_only": True,
    "fixture_only": True,
    "preview_only": True,
    "advisory_only": True,
    "requires_human_review": True,
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


def report_date_from_title(title: Any, fallback: Any) -> str | None:
    if isinstance(fallback, str) and fallback:
        return fallback
    if isinstance(title, str):
        match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", title)
        if match:
            return match.group(1)
    return None


def source_export_summary(source_path: Path, export_result: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(export_result.get("validation_summary"))
    manifest = as_dict(export_result.get("preview_manifest"))
    package = as_dict(export_result.get("preview_package"))
    renderer = as_dict(export_result.get("renderer_source_summary"))
    return {
        "source_path": str(source_path),
        "source_schema_version": export_result.get("schema_version"),
        "source_task_id": export_result.get("task_id"),
        "source_run_id": export_result.get("run_id"),
        "source_generated_at": export_result.get("generated_at"),
        "source_mode": export_result.get("mode"),
        "source_decision": export_result.get("decision"),
        "source_ok": export_result.get("ok") is True,
        "source_preview_id": package.get("preview_id") or manifest.get("preview_id"),
        "source_package_id": package.get("package_id") or manifest.get("package_id"),
        "source_title": package.get("export_title") or renderer.get("source_report_title"),
        "source_report_date": renderer.get("source_report_date"),
        "source_section_count": validation.get("section_count"),
        "source_warning_count": len(as_list(validation.get("warnings"))),
        "source_manifest_included": isinstance(export_result.get("preview_manifest"), dict),
        "source_markdown_included": isinstance(export_result.get("markdown_preview"), str)
        and bool(str(export_result.get("markdown_preview")).strip()),
    }


def build_preview_entry(
    source_path: Path,
    export_result: dict[str, Any],
    source_summary: dict[str, Any],
) -> dict[str, Any]:
    files = as_dict(export_result.get("preview_files"))
    validation = as_dict(export_result.get("validation_summary"))
    package = as_dict(export_result.get("preview_package"))
    manifest = as_dict(export_result.get("preview_manifest"))
    renderer = as_dict(export_result.get("renderer_source_summary"))
    warnings = [str(item) for item in as_list(validation.get("warnings"))]
    title = package.get("export_title") or renderer.get("source_report_title")
    return {
        "preview_id": source_summary.get("source_preview_id"),
        "report_date": report_date_from_title(title, renderer.get("source_report_date")),
        "title": title,
        "manifest_ref": files.get("manifest_json") or "embedded:preview_manifest",
        "markdown_ref": files.get("markdown_preview") or "embedded:markdown_preview",
        "renderer_source_ref": renderer.get("source_path"),
        "section_count": validation.get("section_count"),
        "advisory_only": as_dict(export_result.get("safety")).get("advisory_only") is True,
        "preview_only": as_dict(export_result.get("safety")).get("preview_only") is True,
        "requires_human_review": as_dict(export_result.get("safety")).get("requires_human_review") is True,
        "warnings": warnings,
        "validation_summary": {
            "source_export_ref": str(source_path),
            "source_schema_matched": export_result.get("schema_version") == SOURCE_SCHEMA_VERSION,
            "source_ok": export_result.get("ok") is True,
            "source_mode_fixture_dry_run": export_result.get("mode") == "fixture_dry_run",
            "manifest_ref_present": bool(files.get("manifest_json")) or isinstance(manifest, dict),
            "markdown_ref_present": bool(files.get("markdown_preview"))
            or bool(str(export_result.get("markdown_preview", "")).strip()),
            "renderer_source_ref_present": isinstance(renderer.get("source_path"), str)
            and bool(renderer.get("source_path")),
            "section_count": validation.get("section_count"),
            "warning_count": len(warnings),
        },
    }


def build_summary_entry(entry: dict[str, Any], source_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "preview_id": entry.get("preview_id"),
        "report_date": entry.get("report_date"),
        "title": entry.get("title"),
        "section_count": entry.get("section_count"),
        "warning_count": len(as_list(entry.get("warnings"))),
        "advisory_only": entry.get("advisory_only") is True,
        "preview_only": entry.get("preview_only") is True,
        "requires_human_review": entry.get("requires_human_review") is True,
        "source_decision": source_summary.get("source_decision"),
        "discoverable_refs": {
            "manifest_ref": entry.get("manifest_ref"),
            "markdown_ref": entry.get("markdown_ref"),
            "renderer_source_ref": entry.get("renderer_source_ref"),
        },
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source_path = resolve_repo_path(as_dict(data.get("input_sources")).get("static_preview_export_result_path"))
    export_result = load_json(source_path)
    config = as_dict(data.get("index_config"))
    source_summary = source_export_summary(source_path, export_result)
    entry = build_preview_entry(source_path, export_result, source_summary)
    summary_entry = build_summary_entry(entry, source_summary)
    warnings = sorted(set(str(item) for item in as_list(entry.get("warnings"))))
    validation_summary = {
        "source_schema_expected": SOURCE_SCHEMA_VERSION,
        "source_schema_matched": source_summary.get("source_schema_version") == SOURCE_SCHEMA_VERSION,
        "source_ok": source_summary.get("source_ok") is True,
        "source_mode_fixture_dry_run": source_summary.get("source_mode") == "fixture_dry_run",
        "preview_entry_count": 1,
        "preview_entries_included": True,
        "preview_summary_included": True,
        "manifest_refs_present": bool(entry.get("manifest_ref")),
        "markdown_refs_present": bool(entry.get("markdown_ref")),
        "renderer_source_refs_present": bool(entry.get("renderer_source_ref")),
        "section_count": entry.get("section_count"),
        "deterministic_output": True,
        "fixture_only": True,
        "warnings": warnings,
    }
    preview_summary = {
        "summary_title": config.get("summary_title", "Daily Report Preview Index"),
        "preview_count": 1,
        "warning_count": len(warnings),
        "requires_human_review_count": 1 if entry.get("requires_human_review") is True else 0,
        "entries": [summary_entry],
    }
    preview_index = {
        "index_id": config.get("index_id", "daily_report_preview_index"),
        "source_preview_export_ref": str(source_path),
        "entry_count": 1,
        "manifest_refs": [entry.get("manifest_ref")],
        "markdown_refs": [entry.get("markdown_ref")],
        "renderer_source_refs": [entry.get("renderer_source_ref")],
        "preview_ids": [entry.get("preview_id")],
        "dashboard_summary_ref": "embedded:preview_summary",
    }
    ok = (
        validation_summary["source_schema_matched"]
        and validation_summary["source_ok"]
        and validation_summary["source_mode_fixture_dry_run"]
        and validation_summary["manifest_refs_present"]
        and validation_summary["markdown_refs_present"]
        and validation_summary["renderer_source_refs_present"]
        and all(value is False for value in SIDE_EFFECTS.values())
        and all(value is True for value in SAFETY.values())
    )
    decision = "daily_report_preview_index_completed_with_warnings" if warnings else "daily_report_preview_index_completed"
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-086"),
        "run_id": data.get("run_id", "daily-report-preview-index-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "preview_index": preview_index,
        "preview_entries": [entry],
        "preview_summary": preview_summary,
        "source_preview_export_summary": source_summary,
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision if ok else "validation_failed",
        "next_recommendation": "Use this deterministic index as the discovery fixture for future dashboard, email, or LINE preview integrations after human review.",
    }


def write_json(payload: dict[str, Any], output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Daily Report Preview Index V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["preview_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
