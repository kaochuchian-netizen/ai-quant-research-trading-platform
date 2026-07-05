#!/usr/bin/env python3
"""Build deterministic Official Primary Source Context Admission artifact."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.official_sources.builder import build_official_primary_source_context_admission_artifact


def load_payload(input_path: Path | None) -> dict:
    if input_path:
        return json.loads(input_path.read_text(encoding="utf-8"))
    return {
        "schema_version": "official_primary_source_context_admission_input_v1",
        "task_id": "AI-DEV-141",
        "generated_at": "2026-07-05T00:00:00Z",
        "mode": "deterministic_offline_sample",
        "external_api_calls_allowed": False,
        "secrets_read_allowed": False,
        "production_connector_modification_allowed": False,
        "integration_target_templates": [
            "templates/prediction_context_artifact.example.json",
            "templates/unified_explainability_artifact.example.json",
            "templates/context_based_report_assembly_artifact.example.json",
            "templates/dashboard_decision_intelligence_artifact.example.json",
            "templates/decision_quality_feedback_artifact.example.json",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write-input-template", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    payload = load_payload(args.input)
    if args.write_input_template:
        args.write_input_template.parent.mkdir(parents=True, exist_ok=True)
        args.write_input_template.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    artifact = build_official_primary_source_context_admission_artifact(payload)
    text = json.dumps(artifact, indent=2 if args.pretty else None, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
