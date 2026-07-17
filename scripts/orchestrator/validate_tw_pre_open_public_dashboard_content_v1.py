#!/usr/bin/env python3
"""Validate immutable archive and market-alias content parity for TW 07:00."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestrator.validate_tw_pre_open_0700_structured_payload_v1 import validate as validate_structured


def validate() -> dict:
    structured = validate_structured()
    checks = {
        "structured_gate": structured["ok"],
        "tracking_rendered_parity": structured["tracking_stock_count"] == structured["rendered_card_count"],
        "immutable_payload_hash_present": bool(structured.get("payload_hash")),
        "no_production_publish": structured["production_publish"] is False,
        "no_notification": not structured["email_attempted"] and not structured["line_attempted"],
    }
    return {"ok": all(checks.values()), "checks": checks, "evidence": structured}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
