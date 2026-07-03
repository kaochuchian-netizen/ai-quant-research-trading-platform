#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.market_regime.artifact_builder import build_market_regime_artifact
from app.market_regime.classifier import classify_market_regime
from app.market_regime.schemas import SUPPORTED_REASON_CODES, SUPPORTED_REGIMES
from app.market_regime.sample_data import offline_sample_input

REQUIRED_FILES = [
    "app/market_regime/__init__.py",
    "app/market_regime/schemas.py",
    "app/market_regime/sample_data.py",
    "app/market_regime/classifier.py",
    "app/market_regime/artifact_builder.py",
    "scripts/orchestrator/build_market_regime_artifact.py",
    "scripts/orchestrator/validate_market_regime_intelligence_v1.py",
    "templates/market_regime_input.example.json",
    "templates/market_regime_artifact.example.json",
    "docs/ai_dev_130_market_regime_intelligence_foundation_v1.md",
    "docs/runbooks/market_regime_intelligence_runbook.md",
]

def expect(condition: bool, reasons: list[str], message: str) -> None:
    if not condition:
        reasons.append(message)

def run_builder() -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, "scripts/orchestrator/build_market_regime_artifact.py"],
        cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    try:
        return proc.returncode, json.loads(proc.stdout)
    except Exception:
        return proc.returncode, {"parse_error": proc.stderr or proc.stdout}

def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-130 market regime intelligence V1")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    reasons: list[str] = []

    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    expect(not missing, reasons, f"missing required files: {missing}")

    input_example = json.loads((ROOT / "templates/market_regime_input.example.json").read_text(encoding="utf-8")) if (ROOT / "templates/market_regime_input.example.json").exists() else {}
    artifact_example = json.loads((ROOT / "templates/market_regime_artifact.example.json").read_text(encoding="utf-8")) if (ROOT / "templates/market_regime_artifact.example.json").exists() else {}
    expect(input_example.get("schema_version") == "market_regime_input_v1", reasons, "input example schema_version invalid")
    expect(artifact_example.get("schema_version") == "market_regime_artifact_v1", reasons, "artifact example schema_version invalid")

    cases = {
        "trend_up": {"sample_size": 20, "metrics": {"index_return_20d": 0.07, "realized_volatility_20d": 0.15, "advance_decline_ratio": 1.22, "max_drawdown_20d": -0.03}},
        "trend_down": {"sample_size": 20, "metrics": {"index_return_20d": -0.07, "realized_volatility_20d": 0.16, "advance_decline_ratio": 0.82, "max_drawdown_20d": -0.04}},
        "range_bound": {"sample_size": 20, "metrics": {"index_return_20d": 0.005, "realized_volatility_20d": 0.12, "advance_decline_ratio": 1.0, "max_drawdown_20d": -0.025}},
        "high_volatility": {"sample_size": 20, "metrics": {"index_return_20d": 0.01, "realized_volatility_20d": 0.34, "advance_decline_ratio": 1.0, "max_drawdown_20d": -0.05}},
        "risk_on": {"sample_size": 20, "metrics": {"index_return_20d": 0.08, "realized_volatility_20d": 0.17, "advance_decline_ratio": 1.42, "max_drawdown_20d": -0.02}},
        "risk_off": {"sample_size": 20, "metrics": {"index_return_20d": -0.09, "realized_volatility_20d": 0.24, "advance_decline_ratio": 0.78, "max_drawdown_20d": -0.10}},
        "insufficient_data": {"sample_size": 3, "metrics": {"index_return_20d": 0.01}},
    }
    observed = {}
    for expected, payload in cases.items():
        payload = {"schema_version": "market_regime_input_v1", "as_of_date": "2026-07-03", "market": "TWSE", "source_kind": "offline_sample", **payload}
        result = classify_market_regime(payload).to_dict()
        observed[expected] = result
        expect(result["regime"] in SUPPORTED_REGIMES, reasons, f"unsupported regime: {result['regime']}")
        expect(0.0 <= result["confidence"] <= 1.0, reasons, f"confidence out of range for {expected}")
        expect(all(code in SUPPORTED_REASON_CODES for code in result["reason_codes"]), reasons, f"unsupported reason code for {expected}")
    for expected in cases:
        expect(observed[expected]["regime"] == expected, reasons, f"expected {expected}, got {observed[expected]['regime']}")

    artifact = build_market_regime_artifact(offline_sample_input())
    for key in ["schema_version", "generated_at", "input_summary", "regime_result", "regime_history_readiness", "integration_notes", "safety_summary", "advisory_only"]:
        expect(key in artifact, reasons, f"artifact missing required field: {key}")
    expect(artifact["regime_result"]["regime"] in SUPPORTED_REGIMES, reasons, "artifact regime enum invalid")
    expect(0.0 <= artifact["regime_result"]["confidence"] <= 1.0, reasons, "artifact confidence out of range")
    expect(artifact["safety_summary"].get("line_sent") is False, reasons, "LINE must not be sent")
    expect(artifact["safety_summary"].get("email_sent") is False, reasons, "Email must not be sent")
    expect(artifact["safety_summary"].get("dashboard_published") is False, reasons, "Dashboard must not be published")
    expect(artifact["safety_summary"].get("production_db_write") is False, reasons, "Production DB must not be written")
    expect(artifact["safety_summary"].get("trading_execution") is False, reasons, "Trading must not execute")

    rc, built = run_builder()
    expect(rc == 0 and built.get("schema_version") == "market_regime_artifact_v1", reasons, "builder must print valid artifact JSON")

    result = {
        "ok": not reasons,
        "passed": not reasons,
        "reasons": reasons,
        "checks": {
            "required_files": len(REQUIRED_FILES) - len(missing),
            "supported_regimes": sorted(SUPPORTED_REGIMES),
            "observed_regimes": {key: value["regime"] for key, value in observed.items()},
            "builder_regime": built.get("regime_result", {}).get("regime") if isinstance(built, dict) else None,
            "builder_confidence": built.get("regime_result", {}).get("confidence") if isinstance(built, dict) else None,
        },
        "side_effects": {
            "production_pipeline_run": False,
            "line_sent": False,
            "email_sent": False,
            "dashboard_published": False,
            "secrets_read": False,
            "production_db_write": False,
            "trading_execution_run": False,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if not reasons else 2

if __name__ == "__main__":
    raise SystemExit(main())
