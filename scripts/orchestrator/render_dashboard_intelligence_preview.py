#!/usr/bin/env python3
"""Render Dashboard Intelligence V1 static preview."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from app.dashboard.intelligence_builder import build_artifact, offline_sample_input
from app.dashboard.preview_renderer import FORBIDDEN_OUTPUT_PREFIX, render_preview_html

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--offline-sample", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8")) if args.input else offline_sample_input()
    artifact = build_artifact(payload)
    html = render_preview_html(artifact)
    output = args.output or (REPO_ROOT / "templates/dashboard_intelligence_preview.example.html")
    if str(output).startswith(FORBIDDEN_OUTPUT_PREFIX):
        raise SystemExit("refusing to write production dashboard path")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    summary = {"ok": True, "preview_path": str(output), "bytes": len(html.encode('utf-8')), "production_publish_allowed": False, "section_count": len(artifact.get("sections", [])), "stock_card_count": len(artifact.get("stock_cards", []))}
    print(json.dumps(summary, indent=2 if args.pretty else None, sort_keys=True, ensure_ascii=False))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
