#!/usr/bin/env python3
"""Run deterministic positive, negative and repository governance validation."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from inspect_pending_natural_verification import inspect as inspect_pending
from validate_ai_dev_task_package_v2 import validate as validate_task
from validate_completion_report import validate as validate_completion
from validate_phase_registry import validate as validate_phases
from validate_platform_health_score import validate as validate_health

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs/governance"
CONFIG = ROOT / "config/governance"

REQUIRED_DOCS = (
    "README.md", "platform_roadmap.md", "ai_dev_task_template.md", "definition_of_done_v2.md",
    "product_quality_gate.md", "natural_verification_policy.md", "phase_completion_standard.md",
    "completion_report_template.md", "platform_health_score.md",
)


def run() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    checks["required_documents"] = all((DOCS / name).is_file() and (DOCS / name).stat().st_size > 200 for name in REQUIRED_DOCS)
    for name in ("ai_dev_new_feature.md", "ai_dev_bug_fix.md", "ai_dev_pending_natural_verification.md"):
        result = validate_task(DOCS / "examples" / name)
        checks[f"positive_task:{name}"] = result["ok"]
    completion = validate_completion(DOCS / "examples/completion_report_closed.md")
    checks["positive_completion_report"] = completion["ok"]
    phases = validate_phases(CONFIG / "platform_phase_status.json")
    health = validate_health(CONFIG / "platform_health_score.json")
    pending = inspect_pending(CONFIG / "pending_natural_verification.json", __import__("datetime").date(2026, 7, 28))
    checks["phase_registry"] = phases["ok"]
    checks["health_score"] = health["ok"]
    checks["pending_registry"] = pending["ok"] and pending["pending_is_not_failure"]
    details.update({"phase": phases, "health": health, "pending": pending})
    with tempfile.TemporaryDirectory(prefix="ai-dev-000-governance-") as raw:
        temp = Path(raw)
        bad_task = temp / "bad_task.md"; bad_task.write_text("# Task\nTask ID: wrong\n## Scope\nOnly scope.\n", encoding="utf-8")
        bad_report = temp / "bad_report.md"; bad_report.write_text("# Report\nTask ID: AI-DEV-999\n## Final Status\nCLOSED\n## Natural Verification\nPending natural verification.\n", encoding="utf-8")
        bad_phase = temp / "phase.json"; phase_data = json.loads((CONFIG / "platform_phase_status.json").read_text()); phase_data["phases"][0]["status"] = "CLOSED"; bad_phase.write_text(json.dumps(phase_data), encoding="utf-8")
        bad_health = temp / "health.json"; health_data = json.loads((CONFIG / "platform_health_score.json").read_text()); health_data["dimensions"].pop(); bad_health.write_text(json.dumps(health_data), encoding="utf-8")
        bad_pending = temp / "pending.json"; pending_data = json.loads((CONFIG / "pending_natural_verification.json").read_text()); pending_data["records"][0]["required_windows"] = []; bad_pending.write_text(json.dumps(pending_data), encoding="utf-8")
        checks["negative_task_rejected"] = not validate_task(bad_task)["ok"]
        checks["negative_completion_rejected"] = not validate_completion(bad_report)["ok"]
        checks["negative_phase_rejected"] = not validate_phases(bad_phase)["ok"]
        checks["negative_health_rejected"] = not validate_health(bad_health)["ok"]
        checks["negative_pending_rejected"] = not inspect_pending(bad_pending, __import__("datetime").date(2026, 7, 28))["ok"]
    checks["temporary_fixtures_removed"] = not Path(raw).exists()
    return {
        "schema_version": "platform_governance_validation_v1",
        "task_id": "AI-DEV-000",
        "ok": all(checks.values()),
        "checks": checks,
        "details": details,
        "matrix": {"positive": 4, "negative": 5, "deterministic": True},
        "side_effects": {
            "production_pipeline": False, "notifications": False, "trading": False,
            "scheduler": False, "secrets": False, "production_artifacts": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    result = run(); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)); return 0 if result["ok"] else 2


if __name__ == "__main__": raise SystemExit(main())
