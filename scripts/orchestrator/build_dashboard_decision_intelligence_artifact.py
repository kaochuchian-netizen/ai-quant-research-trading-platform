#!/usr/bin/env python3
"""Build deterministic Dashboard Decision Intelligence artifact."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard_intelligence.builder import build_dashboard_decision_intelligence_artifact

DEFAULT_CONTEXT = ROOT / "templates/prediction_context_artifact.example.json"
DEFAULT_EXPLAINABILITY = ROOT / "templates/unified_explainability_artifact.example.json"
DEFAULT_REPORT_ASSEMBLY = ROOT / "templates/context_based_report_assembly_artifact.example.json"


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def load_payload(input_path: Path | None, context_path: Path | None, explainability_path: Path | None, report_assembly_path: Path | None) -> dict:
    if input_path:
        return json.loads(input_path.read_text(encoding="utf-8"))
    context = context_path or DEFAULT_CONTEXT
    explainability = explainability_path or DEFAULT_EXPLAINABILITY
    report_assembly = report_assembly_path or DEFAULT_REPORT_ASSEMBLY
    return {
        "prediction_context_path": _rel(context),
        "unified_explainability_path": _rel(explainability),
        "context_based_report_assembly_path": _rel(report_assembly),
        "prediction_context": json.loads(context.read_text(encoding="utf-8")),
        "unified_explainability": json.loads(explainability.read_text(encoding="utf-8")),
        "context_based_report_assembly": json.loads(report_assembly.read_text(encoding="utf-8")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--explainability", type=Path)
    parser.add_argument("--report-assembly", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write-input-template", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = load_payload(args.input, args.context, args.explainability, args.report_assembly)
    if args.write_input_template:
        args.write_input_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_input_template.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    artifact = build_dashboard_decision_intelligence_artifact(
        payload["prediction_context"],
        payload["unified_explainability"],
        payload["context_based_report_assembly"],
    )
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
