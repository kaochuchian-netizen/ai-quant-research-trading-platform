#!/usr/bin/env python3
"""Validate the measurable ten-dimension platform health score."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from governance_common import TRENDS, load_json, result_payload

REQUIRED_IDS = (
    "product_quality", "decision_explainability", "data_truthfulness", "evidence_traceability",
    "cross_window_continuity", "cross_channel_parity", "natural_verification", "regression_risk",
    "technical_debt", "phase_completion",
)


def validate(path: Path) -> dict:
    data, errors = load_json(path)
    dimensions = data.get("dimensions", []) if data else []
    if data and data.get("schema_version") != "platform_health_score_v1": errors.append("schema_version")
    ids = tuple(item.get("id") for item in dimensions if isinstance(item, dict))
    if ids != REQUIRED_IDS: errors.append("dimension_identity_or_order")
    total_weight = 0.0; weighted = 0.0
    for item in dimensions:
        if not isinstance(item, dict): errors.append("dimension_object"); continue
        score, target, weight = item.get("score"), item.get("target"), item.get("weight")
        if not isinstance(score, (int, float)) or not 0 <= score <= 100: errors.append(f"score:{item.get('id')}")
        if not isinstance(target, (int, float)) or not 0 <= target <= 100: errors.append(f"target:{item.get('id')}")
        if not isinstance(weight, (int, float)) or weight <= 0: errors.append(f"weight:{item.get('id')}")
        else: total_weight += weight; weighted += float(score or 0) * weight
        if item.get("trend") not in TRENDS: errors.append(f"trend:{item.get('id')}")
        for key in ("name", "description", "measurement", "owner", "evidence"):
            if not isinstance(item.get(key), str) or len(item[key].strip()) < 8: errors.append(f"metadata:{item.get('id')}:{key}")
    calculated = round(weighted / total_weight, 1) if total_weight else None
    if abs(total_weight - 1.0) > 0.0001: errors.append("weights_must_sum_to_one")
    if data and calculated != data.get("overall_score"): errors.append("overall_score_mismatch")
    return result_payload("validate_platform_health_score", errors, {"path": str(path), "dimensions": list(ids), "calculated_overall_score": calculated, "total_weight": round(total_weight, 4)})


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--input", default="config/governance/platform_health_score.json"); parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(); result = validate(Path(args.input)); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)); return 0 if result["ok"] else 2


if __name__ == "__main__": raise SystemExit(main())
