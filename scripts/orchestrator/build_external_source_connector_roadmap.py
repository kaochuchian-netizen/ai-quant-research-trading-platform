#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.source_roadmap.roadmap_builder import build_external_source_connector_roadmap

def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic external source connector roadmap")
    parser.add_argument("--audit")
    parser.add_argument("--output")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    artifact = build_external_source_connector_roadmap(ROOT, args.audit)
    text = json.dumps(artifact, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        out = Path(args.output)
        if str(out).startswith("/var/www/stock-ai-dashboard"):
            raise SystemExit("refusing dashboard production path")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
