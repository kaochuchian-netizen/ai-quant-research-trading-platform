#!/usr/bin/env python3
"""Build deterministic Decision Quality Feedback artifact."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.decision_feedback.builder import build_decision_quality_feedback_artifact

DEFAULT_CONTEXT = ROOT / "templates/prediction_context_artifact.example.json"
DEFAULT_EXPLAINABILITY = ROOT / "templates/unified_explainability_artifact.example.json"
DEFAULT_REPORT_ASSEMBLY = ROOT / "templates/context_based_report_assembly_artifact.example.json"
DEFAULT_DASHBOARD = ROOT / "templates/dashboard_decision_intelligence_artifact.example.json"


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def _sample_factor_rows(explainability: dict) -> list[dict]:
    rows = []
    labels = ["effective", "mixed", "watch", "neutral"]
    for idx, item in enumerate(explainability.get("factor_explanations", [])):
        factor_id = item.get("factor_id") or item.get("id") or f"factor_{idx+1}"
        rows.append({
            "factor_id": factor_id,
            "recent_effectiveness": labels[idx % len(labels)],
            "evidence_support": item.get("supporting_sources") or item.get("source_ids") or [],
            "confidence_support": "sample_support" if idx % 2 == 0 else "sample_watch",
            "warning_flag": idx % 3 == 2,
            "recommended_action": "display_review_hint_no_weight_change",
        })
    return rows


def load_payload(input_path: Path | None, context_path: Path | None, explainability_path: Path | None, report_assembly_path: Path | None, dashboard_path: Path | None) -> dict:
    if input_path:
        return json.loads(input_path.read_text(encoding="utf-8"))
    context = context_path or DEFAULT_CONTEXT
    explainability = explainability_path or DEFAULT_EXPLAINABILITY
    report_assembly = report_assembly_path or DEFAULT_REPORT_ASSEMBLY
    dashboard = dashboard_path or DEFAULT_DASHBOARD
    explainability_payload = json.loads(explainability.read_text(encoding="utf-8"))
    return {
        "feedback_window": "last_7_sessions_sample",
        "prediction_context_path": _rel(context),
        "unified_explainability_path": _rel(explainability),
        "context_based_report_assembly_path": _rel(report_assembly),
        "dashboard_decision_intelligence_path": _rel(dashboard),
        "prediction_context": json.loads(context.read_text(encoding="utf-8")),
        "unified_explainability": explainability_payload,
        "context_based_report_assembly": json.loads(report_assembly.read_text(encoding="utf-8")),
        "dashboard_decision_intelligence": json.loads(dashboard.read_text(encoding="utf-8")),
        "rolling_evaluation_sample": {
            "evaluation_window": "last_7_sessions_sample",
            "sample_count": 7,
            "direction_hit_rate": 0.57,
            "high_range_hit_rate": 0.43,
            "low_range_hit_rate": 0.50,
            "bias_summary": "Sample indicates mild range-width bias; review before any production use.",
            "insufficient_data_flag": False,
        },
        "prediction_review_sample": {
            "reviewed_predictions": 5,
            "pending_predictions": 2,
            "insufficient_actuals": 0,
            "major_error_cases": ["sample_gap_up_outlier"],
            "review_quality_flag": "sample_review_only",
        },
        "factor_effectiveness_sample": _sample_factor_rows(explainability_payload),
        "confidence_calibration_sample": {
            "calibration_window": "last_7_sessions_sample",
            "overconfidence_flag": True,
            "underconfidence_flag": False,
            "confidence_bias": "sample_slight_overconfidence",
            "recommended_confidence_note": "Display confidence caution in report/dashboard; do not change production confidence.",
        },
        "market_regime_quality_sample": {
            "regime": "sample_range_bound",
            "regime_confidence": "medium_sample",
            "regime_specific_performance_note": "Range forecasts need wider interval review in this sample regime.",
            "regime_caution": "Market regime sample suggests caution on narrow high/low intervals.",
            "recommended_report_note": "Add regime caution to future report feedback display.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--explainability", type=Path)
    parser.add_argument("--report-assembly", type=Path)
    parser.add_argument("--dashboard", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write-input-template", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = load_payload(args.input, args.context, args.explainability, args.report_assembly, args.dashboard)
    if args.write_input_template:
        args.write_input_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_input_template.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    artifact = build_decision_quality_feedback_artifact(payload)
    text = json.dumps(artifact, indent=2 if args.pretty else None, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        if str(args.output).startswith("/var/www/stock-ai-dashboard"):
            raise SystemExit("refusing dashboard production path")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
