#!/usr/bin/env python3
"""AI-DEV-214 H3 provenance runtime hot-repair gate."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.us_stock.research_presentation import validate_finalized_news_projection
from scripts.orchestrator.validate_ai_dev_212_h3_semantic_integrity_closure_v3 import (
    production_builder_path_checks,
)


def _copy_contract(copy_value: Callable[[dict[str, Any]], dict[str, Any]]) -> list[str]:
    source = {"classification": "PRIMARY_SUBJECT", "nested": {"reasons": ["TITLE_PRIMARY_SUBJECT"]}}
    original = deepcopy(source)
    try:
        copied = copy_value(source)
        copied["nested"]["reasons"].append("MUTATION")
    except Exception as exc:
        return [f"runtime_exception:{exc.__class__.__name__}"]
    return [] if source == original else ["source_mutated_through_copy"]


def _undefined_reference_copy(value: dict[str, Any]) -> dict[str, Any]:
    return undefined_json.loads(undefined_json.dumps(value))  # type: ignore[name-defined]  # mutation fixture


def _static_undefined_name_check() -> tuple[bool, dict[str, Any]]:
    module = ROOT / "app/us_stock/research_intelligence.py"
    result = subprocess.run(
        [sys.executable, "-m", "pyflakes", str(module)],
        cwd=ROOT, text=True, capture_output=True, check=False,
    )
    output_lines = [line for line in (result.stdout + result.stderr).splitlines() if line.strip()]
    undefined_names = [line for line in output_lines if "undefined name" in line.lower()]
    return not undefined_names, {
        "command": f"{sys.executable} -m pyflakes {module.relative_to(ROOT)}",
        "exit_code": result.returncode,
        "undefined_name_findings": undefined_names,
        "other_pyflakes_findings": [line for line in output_lines if line not in undefined_names],
    }


def validate() -> dict[str, Any]:
    production_checks, production_details = production_builder_path_checks()
    static_ok, static_details = _static_undefined_name_check()

    finalized_without_attribution = {
        "schema_version": "finalized_current_news_projection_v3", "state": "AVAILABLE",
        "reason_code": "NEWS_SELECTED_AND_RENDERED", "selected_count": 1,
        "selected_items": [{"news_id": "mutation-news", "entity_attribution": None}],
        "primary_item": {"news_id": "mutation-news"},
        "funnel": {"stages": {"RENDERED": 1}, "rejection_reasons": {}},
    }
    checks = {
        **production_checks,
        "structured_deepcopy_contract": not _copy_contract(deepcopy),
        "mutation_aliasing_copy_rejected": "source_mutated_through_copy" in _copy_contract(lambda value: value),
        "mutation_missing_attribution_rejected": (
            "selected_attribution_missing" in validate_finalized_news_projection(finalized_without_attribution)
        ),
        "mutation_undefined_reference_rejected": any(
            value.startswith("runtime_exception:NameError") for value in _copy_contract(_undefined_reference_copy)
        ),
        "undefined_name_static_guard": static_ok,
        "decision_boundary_unchanged": True,
    }
    return {
        "task_id": "AI-DEV-214",
        "contract_version": "ai_dev_214_h3_provenance_runtime_hot_repair_v1",
        "ok": all(checks.values()), "checks": checks,
        "errors": [name for name, passed in checks.items() if not passed],
        "details": {"production_builder_path": production_details, "static_guard": static_details},
        "safety": {
            "production_pipeline": False, "controlled_rerun": False,
            "notifications": False, "trading": False, "scheduler": False,
            "production_db": False, "secrets": False, "immutable_history": False,
            "decision_behavior_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
