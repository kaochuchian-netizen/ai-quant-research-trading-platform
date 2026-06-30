#!/usr/bin/env python3
"""Build a deterministic Daily Report Intelligence Integration V1 fixture."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_intelligence_integration_input.example.json")
CONTRACT_NAME = "daily_report_intelligence_integration"
CONTRACT_VERSION = "v1"
SCHEMA_VERSION = "daily_report_intelligence_integration_v1"
COMPANY_SCHEMA_VERSION = "company_intelligence_source_credibility_v1"
INDUSTRY_SCHEMA_VERSION = "industry_intelligence_peer_context_v1"
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
        resolve_repo_path(sources.get("company_intelligence_result_path")),
        resolve_repo_path(sources.get("industry_peer_context_result_path")),
    )


def average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def score_values(items: list[Any]) -> list[float]:
    return [
        float(item.get("credibility_score"))
        for item in items
        if isinstance(item, dict) and isinstance(item.get("credibility_score"), (int, float))
    ]


def company_summary(company_result: dict[str, Any]) -> dict[str, Any]:
    intelligence = as_dict(company_result.get("company_intelligence"))
    summary = as_dict(intelligence.get("summary"))
    company = as_dict(company_result.get("company"))
    items = [item for item in as_list(intelligence.get("items")) if isinstance(item, dict)]
    return {
        "source_schema_version": company_result.get("schema_version"),
        "source_task_id": company_result.get("task_id"),
        "source_run_id": company_result.get("run_id"),
        "source_decision": company_result.get("decision"),
        "company": {
            "stock_id": company.get("stock_id"),
            "stock_name": company.get("stock_name"),
            "market": company.get("market"),
            "industry": company.get("industry"),
        },
        "topic_count": summary.get("topic_count", len(items)),
        "average_source_credibility_score": summary.get("average_source_credibility_score"),
        "low_credibility_source_ids": deepcopy(summary.get("low_credibility_source_ids", [])),
        "summary_points": [str(item.get("summary")) for item in items if item.get("summary")][:3],
        "advisory_only": True,
        "requires_human_review": True,
    }


def industry_summary(industry_result: dict[str, Any]) -> dict[str, Any]:
    summary = as_dict(industry_result.get("industry_peer_context_summary"))
    industry = as_dict(industry_result.get("industry"))
    target = as_dict(industry_result.get("target_company"))
    return {
        "source_schema_version": industry_result.get("schema_version"),
        "source_task_id": industry_result.get("task_id"),
        "source_run_id": industry_result.get("run_id"),
        "source_decision": industry_result.get("decision"),
        "industry": {
            "industry_id": industry.get("industry_id"),
            "industry_name": industry.get("industry_name"),
            "as_of_date": industry.get("as_of_date"),
        },
        "target_company": {
            "stock_id": target.get("stock_id"),
            "stock_name": target.get("stock_name"),
            "market": target.get("market"),
            "industry": target.get("industry"),
        },
        "industry_topic_count": summary.get("industry_topic_count"),
        "peer_context_count": summary.get("peer_context_count"),
        "average_confidence": summary.get("average_confidence"),
        "highest_risk_flags": deepcopy(summary.get("highest_risk_flags", [])),
        "summary_points": deepcopy(summary.get("summary_points", [])),
        "advisory_only": True,
        "requires_human_review": True,
    }


def source_credibility_summary(company_result: dict[str, Any], industry_result: dict[str, Any]) -> dict[str, Any]:
    company_scores = [item for item in as_list(company_result.get("source_credibility_scores")) if isinstance(item, dict)]
    industry_scores = [item for item in as_list(industry_result.get("source_credibility_scores")) if isinstance(item, dict)]
    combined = company_scores + industry_scores
    low_credibility_ids = sorted({
        str(item.get("source_id"))
        for item in combined
        if isinstance(item.get("credibility_score"), (int, float)) and float(item["credibility_score"]) < 0.50
    })
    review_required_ids = sorted({
        str(item.get("source_id"))
        for item in combined
        if item.get("requires_human_review") is True
    })
    core_allowed_ids = sorted({
        str(item.get("source_id"))
        for item in combined
        if item.get("core_scoring_allowed") is True
    })
    return {
        "company_source_count": len(company_scores),
        "industry_peer_source_count": len(industry_scores),
        "combined_source_count": len(combined),
        "average_credibility_score": average(score_values(combined)),
        "low_credibility_source_ids": low_credibility_ids,
        "review_required_source_ids": review_required_ids,
        "core_scoring_allowed_source_ids": core_allowed_ids,
        "metadata_preserved": True,
        "source_credibility_scores": deepcopy(combined),
        "advisory_only": True,
        "requires_human_review": True,
    }


def build_markdown(
    title: str,
    company: dict[str, Any],
    industry: dict[str, Any],
    credibility: dict[str, Any],
    risk_and_limitations: list[str],
) -> str:
    lines = [
        f"## {title}",
        "",
        "> Fixture-only intelligence section. Advisory only; human review is required before daily report insertion.",
        "",
        "### Company Intelligence",
    ]
    for point in as_list(company.get("summary_points")):
        lines.append(f"- {point}")
    lines.extend(["", "### Industry And Peer Context"])
    for point in as_list(industry.get("summary_points"))[:4]:
        lines.append(f"- {point}")
    lines.extend([
        "",
        "### Source Credibility",
        f"- Combined source count: `{credibility.get('combined_source_count')}`",
        f"- Average credibility score: `{credibility.get('average_credibility_score')}`",
        f"- Human-review source count: `{len(as_list(credibility.get('review_required_source_ids')))}`",
        "",
        "### Risk And Limitations",
    ])
    for item in risk_and_limitations:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("_No delivery action, portfolio action, schedule change, or persistent store write was performed._")
    return "\n".join(lines)


def build_section(
    data: dict[str, Any],
    company: dict[str, Any],
    industry: dict[str, Any],
    credibility: dict[str, Any],
    risk_and_limitations: list[str],
) -> dict[str, Any]:
    config = as_dict(data.get("daily_report_section_config"))
    title = str(config.get("title", "Company And Industry Intelligence"))
    markdown = build_markdown(title, company, industry, credibility, risk_and_limitations)
    return {
        "section_id": config.get("section_id", "daily_report_intelligence"),
        "section_type": "daily_report_intelligence",
        "title": title,
        "placement": config.get("placement", "after_strategy_summary"),
        "priority": config.get("priority", "medium"),
        "render_mode": "static_markdown_with_machine_readable_payload",
        "markdown": markdown,
        "machine_readable": {
            "company_intelligence_summary": deepcopy(company),
            "industry_peer_context_summary": deepcopy(industry),
            "source_credibility_summary": {
                key: deepcopy(value)
                for key, value in credibility.items()
                if key != "source_credibility_scores"
            },
            "risk_and_limitations": deepcopy(risk_and_limitations),
            "advisory_only": True,
            "requires_human_review": True,
        },
        "badges": {
            "repo_only": True,
            "fixture_only": True,
            "advisory_only": True,
            "requires_human_review": True,
        },
        "source_refs": [
            "input_sources.company_intelligence_result_path",
            "input_sources.industry_peer_context_result_path",
        ],
        "advisory_only": True,
        "requires_human_review": True,
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    company_path, industry_path = source_paths(data)
    company_result = load_json(company_path)
    industry_result = load_json(industry_path)
    company = company_summary(company_result)
    industry = industry_summary(industry_result)
    credibility = source_credibility_summary(company_result, industry_result)
    risk_and_limitations = [
        "Fixture summaries are static examples and are not connected to live report generation.",
        "This section is advisory only and must not be treated as investment advice.",
        "Lower-credibility and human-review sources remain labeled and must be reviewed before use.",
        "No portfolio, delivery, schedule, model, or market data action is authorized by this output.",
    ]
    source_summary = {
        "company_source_schema_version": company_result.get("schema_version"),
        "industry_peer_source_schema_version": industry_result.get("schema_version"),
        "company_source_run_id": company_result.get("run_id"),
        "industry_peer_source_run_id": industry_result.get("run_id"),
        "company_source_decision": company_result.get("decision"),
        "industry_peer_source_decision": industry_result.get("decision"),
        "company_source_ok": company_result.get("ok") is True,
        "industry_peer_source_ok": industry_result.get("ok") is True,
        "source_paths": {
            "company_intelligence_result_path": str(company_path),
            "industry_peer_context_result_path": str(industry_path),
        },
    }
    warnings = []
    if company_result.get("schema_version") != COMPANY_SCHEMA_VERSION:
        warnings.append("company source schema mismatch")
    if industry_result.get("schema_version") != INDUSTRY_SCHEMA_VERSION:
        warnings.append("industry peer source schema mismatch")
    if credibility["review_required_source_ids"]:
        warnings.append("human review required for one or more sources")
    ok = not warnings or warnings == ["human review required for one or more sources"]
    decision = "daily_report_intelligence_integration_completed_with_warnings" if warnings else "daily_report_intelligence_integration_completed"
    return {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-082"),
        "run_id": data.get("run_id", "daily-report-intelligence-integration-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "source_summary": source_summary,
        "daily_report_intelligence_section": build_section(data, company, industry, credibility, risk_and_limitations),
        "company_intelligence_summary": company,
        "industry_peer_context_summary": industry,
        "source_credibility_summary": credibility,
        "risk_and_limitations": risk_and_limitations,
        "validation_summary": {
            "contract_name": CONTRACT_NAME,
            "contract_version": CONTRACT_VERSION,
            "company_schema_expected": COMPANY_SCHEMA_VERSION,
            "industry_peer_schema_expected": INDUSTRY_SCHEMA_VERSION,
            "company_schema_matched": company_result.get("schema_version") == COMPANY_SCHEMA_VERSION,
            "industry_peer_schema_matched": industry_result.get("schema_version") == INDUSTRY_SCHEMA_VERSION,
            "markdown_included": True,
            "machine_readable_included": True,
            "source_credibility_metadata_preserved": credibility["metadata_preserved"],
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
        "next_recommendation": "Review this static section contract before inserting it into any scheduled daily report.",
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
    parser = argparse.ArgumentParser(description="Build Daily Report Intelligence Integration V1 fixture.")
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
        write_text(str(result["daily_report_intelligence_section"]["markdown"]) + "\n", Path(args.markdown_output))
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
