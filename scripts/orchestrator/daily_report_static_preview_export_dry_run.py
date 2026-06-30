#!/usr/bin/env python3
"""Build a deterministic Daily Report Static Preview Export V1 fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_static_preview_export_input.example.json")
SCHEMA_VERSION = "daily_report_static_preview_export_v1"
RENDERER_SCHEMA_VERSION = "daily_report_renderer_contract_v1"
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


def stable_json(payload: Any, pretty: bool = True) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    return f"{text}\n" if pretty else text


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def section_index(renderer_result: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, section in enumerate(as_list(renderer_result.get("report_sections")), start=1):
        if not isinstance(section, dict):
            continue
        result.append(
            {
                "index": index,
                "section_id": section.get("section_id"),
                "title": section.get("title"),
                "placement": section.get("placement"),
                "priority": section.get("priority"),
                "source_refs": deepcopy(section.get("source_refs", [])),
                "advisory_only": section.get("advisory_only") is True,
                "requires_human_review": section.get("requires_human_review") is True,
                "markdown_char_count": len(str(section.get("markdown", ""))),
                "machine_readable_included": isinstance(section.get("machine_readable"), dict),
            }
        )
    return result


def renderer_source_summary(source_path: Path, renderer_result: dict[str, Any]) -> dict[str, Any]:
    validation = as_dict(renderer_result.get("validation_summary"))
    return {
        "source_path": str(source_path),
        "source_schema_version": renderer_result.get("schema_version"),
        "source_task_id": renderer_result.get("task_id"),
        "source_run_id": renderer_result.get("run_id"),
        "source_generated_at": renderer_result.get("generated_at"),
        "source_mode": renderer_result.get("mode"),
        "source_decision": renderer_result.get("decision"),
        "source_ok": renderer_result.get("ok") is True,
        "source_report_title": renderer_result.get("report_title"),
        "source_report_date": renderer_result.get("report_date"),
        "source_section_order": deepcopy(renderer_result.get("section_order", [])),
        "source_warning_count": len(as_list(validation.get("warnings"))),
        "source_markdown_included": isinstance(renderer_result.get("markdown"), str)
        and bool(str(renderer_result.get("markdown")).strip()),
        "source_render_payload_included": isinstance(renderer_result.get("render_payload"), dict),
    }


def build_markdown_preview(
    export_title: str,
    generated_at: Any,
    manifest_id: str,
    renderer_summary: dict[str, Any],
    sections: list[dict[str, Any]],
    renderer_markdown: str,
    warnings: list[str],
) -> str:
    lines = [
        f"# {export_title}",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Manifest ID: `{manifest_id}`",
        "- Mode: `fixture_dry_run`",
        "- Preview only: `true`",
        "- Advisory only: `true`",
        "",
        "> Static preview package only. No delivery action, external model call, market data call, persistent store write, portfolio action, or schedule/service change was performed.",
        "",
        "## Renderer Source",
        f"- Source path: `{renderer_summary.get('source_path')}`",
        f"- Source run ID: `{renderer_summary.get('source_run_id')}`",
        f"- Source decision: `{renderer_summary.get('source_decision')}`",
        f"- Source warning count: `{renderer_summary.get('source_warning_count')}`",
        "",
        "## Section Index",
    ]
    for section in sections:
        lines.append(
            f"- {section.get('index')}. `{section.get('section_id')}` "
            f"{section.get('title')} ({section.get('placement')}, {section.get('priority')})"
        )
    if warnings:
        lines.extend(["", "## Validation Warnings"])
        for warning in warnings:
            lines.append(f"- {warning}")
    lines.extend(["", "## Renderer Markdown Preview", "", renderer_markdown.strip(), ""])
    return "\n".join(lines)


def build_result(
    data: dict[str, Any],
    output_path: Path | None,
    manifest_output: Path | None,
    markdown_output: Path | None,
) -> dict[str, Any]:
    renderer_path = resolve_repo_path(as_dict(data.get("input_sources")).get("renderer_result_path"))
    renderer_result = load_json(renderer_path)
    config = as_dict(data.get("preview_config"))
    preview_id = str(config.get("preview_id", "daily_report_static_preview"))
    manifest_id = str(config.get("manifest_id", "daily_report_static_preview_manifest"))
    package_id = str(config.get("package_id", "daily_report_static_preview_package"))
    export_title = str(config.get("export_title", "Daily Report Static Preview"))
    sections = section_index(renderer_result)
    source_summary = renderer_source_summary(renderer_path, renderer_result)
    renderer_validation = as_dict(renderer_result.get("validation_summary"))
    warnings = [str(item) for item in as_list(renderer_validation.get("warnings"))]
    if renderer_result.get("decision") == "daily_report_renderer_completed_with_warnings":
        warnings.append("source renderer completed with warnings")
    warnings = sorted(set(warnings))
    markdown_preview = build_markdown_preview(
        export_title,
        data.get("generated_at"),
        manifest_id,
        source_summary,
        sections,
        str(renderer_result.get("markdown", "")),
        warnings,
    )
    validation_summary = {
        "source_schema_expected": RENDERER_SCHEMA_VERSION,
        "source_schema_matched": renderer_result.get("schema_version") == RENDERER_SCHEMA_VERSION,
        "source_ok": renderer_result.get("ok") is True,
        "source_mode_fixture_dry_run": renderer_result.get("mode") == "fixture_dry_run",
        "preview_manifest_included": True,
        "markdown_preview_included": bool(markdown_preview.strip()),
        "section_index_included": bool(sections),
        "section_count": len(sections),
        "source_section_order_preserved": [section.get("section_id") for section in sections]
        == as_list(renderer_result.get("section_order")),
        "validation_summary_included": True,
        "safety_summary_included": True,
        "deterministic_output": True,
        "fixture_only": True,
        "warnings": warnings,
    }
    safety = {
        "repo_only": True,
        "fixture_only": True,
        "advisory_only": True,
        "preview_only": True,
        "requires_human_review": True,
        "no_external_model_calls": True,
        "no_market_data_calls": True,
        "no_delivery_actions": True,
        "no_persistent_store_writes": True,
        "no_portfolio_actions": True,
        "no_schedule_service_changes": True,
    }
    preview_files = {
        "result_json": str(output_path) if output_path else None,
        "manifest_json": str(manifest_output) if manifest_output else None,
        "markdown_preview": str(markdown_output) if markdown_output else None,
        "section_index": "embedded:preview_manifest.section_index",
        "validation_summary": "embedded:validation_summary",
        "safety_summary": "embedded:safety",
    }
    preview_manifest = {
        "schema_version": "daily_report_static_preview_manifest_v1",
        "manifest_id": manifest_id,
        "preview_id": preview_id,
        "package_id": package_id,
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "renderer_source": source_summary,
        "artifacts": {
            "manifest_json": {
                "path": preview_files["manifest_json"],
                "content_type": "application/json",
                "sha256_scope": "omitted_for_self_referential_artifact",
            },
            "result_json": {
                "path": preview_files["result_json"],
                "content_type": "application/json",
                "sha256_scope": "omitted_for_self_referential_artifact",
            },
            "markdown_preview": {
                "path": preview_files["markdown_preview"],
                "content_type": "text/markdown",
                "sha256": sha256_text(markdown_preview + "\n"),
            },
            "section_index": {
                "path": preview_files["section_index"],
                "content_type": "application/json",
                "sha256": sha256_text(stable_json(sections)),
            },
            "validation_summary": {
                "path": preview_files["validation_summary"],
                "content_type": "application/json",
                "sha256": sha256_text(stable_json(validation_summary)),
            },
            "safety_summary": {
                "path": preview_files["safety_summary"],
                "content_type": "application/json",
                "sha256": sha256_text(stable_json(safety)),
            },
        },
        "section_index": sections,
        "validation_summary": validation_summary,
        "safety": safety,
        "delivery_authorized": False,
        "external_runtime_authorized": False,
    }
    ok = (
        validation_summary["source_schema_matched"]
        and validation_summary["source_ok"]
        and validation_summary["source_mode_fixture_dry_run"]
        and validation_summary["markdown_preview_included"]
        and validation_summary["section_index_included"]
        and all(value is False for value in SIDE_EFFECTS.values())
        and all(value is True for value in safety.values())
    )
    decision = "daily_report_static_preview_export_completed_with_warnings" if warnings else "daily_report_static_preview_export_completed"
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-085"),
        "run_id": data.get("run_id", "daily-report-static-preview-export-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "preview_package": {
            "package_id": package_id,
            "preview_id": preview_id,
            "export_title": export_title,
            "renderer_result_path": str(renderer_path),
            "artifact_count": len(preview_manifest["artifacts"]),
            "artifact_names": sorted(preview_manifest["artifacts"]),
            "intended_consumers": ["dashboard_preview", "email_template_review", "line_template_review"],
            "delivery_authorized": False,
        },
        "preview_manifest": preview_manifest,
        "preview_files": preview_files,
        "renderer_source_summary": source_summary,
        "report_sections": sections,
        "markdown_preview": markdown_preview,
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": safety,
        "ok": ok,
        "decision": decision if ok else "validation_failed",
        "next_recommendation": "Review the static preview package before designing any future dashboard, email, or LINE delivery integration.",
    }
    return result


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
    parser = argparse.ArgumentParser(description="Build Daily Report Static Preview Export V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--markdown-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(
        load_json(Path(args.input)),
        Path(args.output),
        Path(args.manifest_output),
        Path(args.markdown_output),
    )
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["preview_manifest"], Path(args.manifest_output), args.pretty)
    write_text(str(result["markdown_preview"]).rstrip() + "\n", Path(args.markdown_output))
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
