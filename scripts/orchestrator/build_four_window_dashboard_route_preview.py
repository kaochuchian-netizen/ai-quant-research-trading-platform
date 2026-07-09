#!/usr/bin/env python3
"""Build controlled four-window dashboard route preview artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.four_window_route_integration import build_artifact, build_input, render_route_html, write_json

DEFAULT_INPUT = ROOT / "templates/four_window_dashboard_route_integration_input.example.json"
DEFAULT_OUTPUT = ROOT / "templates/four_window_dashboard_route_integration.example.json"
DEFAULT_HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
FORBIDDEN_PREFIXES = ["/var/www", "/srv", "/etc"]


def check_output(path: Path) -> None:
    resolved = str(path.resolve())
    if any(resolved.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        raise SystemExit(f"refusing production-like output path: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--html-output", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--write-input-template", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8")) if args.input else build_input()
    artifact = build_artifact(payload, ROOT)
    preview_html = (ROOT / artifact["source_preview_html"]).read_text(encoding="utf-8")
    route_html = render_route_html(artifact, preview_html)
    route_html = "\n".join(line.rstrip() for line in route_html.splitlines()) + "\n"
    check_output(args.output)
    check_output(args.html_output)
    write_json(args.output, artifact)
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(route_html, encoding="utf-8")
    if args.write_input_template:
        write_json(DEFAULT_INPUT, build_input())
    summary = {
        "ok": True,
        "task_id": artifact["task_id"],
        "schema_version": artifact["schema_version"],
        "route_path": artifact["route_path"],
        "window_count": len(artifact["four_window_mapping"]),
        "output": str(args.output),
        "html_output": str(args.html_output),
        "production_dashboard_publish_executed": False,
        "dashboard_published": False,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
