#!/usr/bin/env python3
"""Build deterministic four-window Decision Intelligence dashboard preview artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.four_window_decision_intelligence import build_artifact, build_input, render_html, write_json

DEFAULT_INPUT = ROOT / "templates/four_window_decision_intelligence_dashboard_input.example.json"
DEFAULT_ARTIFACT = ROOT / "templates/four_window_decision_intelligence_dashboard_artifact.example.json"
DEFAULT_HTML = ROOT / "templates/four_window_decision_intelligence_dashboard_preview.example.html"
FORBIDDEN_PREFIXES = ["/var/www", "/srv", "/etc"]


def load_payload(path: Path | None) -> dict:
    if path is None:
        return build_input()
    return json.loads(path.read_text(encoding="utf-8"))


def check_output(path: Path) -> None:
    resolved = str(path.resolve())
    if any(resolved.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        raise SystemExit(f"refusing production-like output path: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--output-html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--write-input-template", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = load_payload(args.input)
    artifact = build_artifact(payload)
    html = render_html(artifact)
    check_output(args.output_json)
    check_output(args.output_html)
    write_json(args.output_json, artifact, pretty=True)
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(html, encoding="utf-8")
    if args.write_input_template:
        write_json(DEFAULT_INPUT, build_input(), pretty=True)
    summary = {
        "ok": True,
        "task_id": artifact["task_id"],
        "schema_version": artifact["schema_version"],
        "window_count": len(artifact["four_window_content_contract"]),
        "common_section_count": len(artifact["common_decision_intelligence_sections"]),
        "json_path": str(args.output_json),
        "html_path": str(args.output_html),
        "dashboard_published": False,
        "external_notification_sent": False,
        "production_pipeline_executed": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
