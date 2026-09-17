#!/usr/bin/env python3
"""AI-DEV-244 post-merge validator timeout and observability regression guard."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.runtime.validator_registry import execute_validator_gate
from scripts.orchestrator.validate_post_merge_status import (
    classify_dirty_paths,
    slow_validator_summary,
    summarize_post_merge_status,
)


def check(name: str, condition: bool, checks: dict[str, bool]) -> None:
    checks[name] = bool(condition)


def entry(validator_id: str, *, role: str = "leaf", required_post: bool = True) -> dict:
    return {
        "validator_id": validator_id,
        "path": f"validators/{validator_id}.py",
        "status": "ACTIVE",
        "execution_role": role,
        "scope": "fixture",
        "introduced_by": "AI-DEV-244",
        "reason": "deterministic timeout fixture",
        "required_in_branch_gate": True,
        "required_in_post_merge": required_post,
        "last_contract_version": "fixture_v1",
    }


def fixture_registry(root: Path, rows: list[dict]) -> Path:
    for row in rows:
        path = root / row["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# fixture validator\n", encoding="utf-8")
    registry = root / "registry.json"
    registry.write_text(
        json.dumps({"schema_version": "validator_registry_v2", "version": "fixture", "validators": rows}),
        encoding="utf-8",
    )
    return registry


def clean_platform() -> dict:
    return {
        "ok": True,
        "warnings": [],
        "open_pr_count": 0,
        "git": {
            "current_branch": "main",
            "head_sha": "abc123",
            "main_sha": "abc123",
            "origin_main_sha": "abc123",
            "clean": True,
            "status_short": [],
            "main_origin_main_sync": {"status": "in_sync", "ahead": 0, "behind": 0},
            "local_branches": ["main"],
            "remote_branches": ["origin/main"],
        },
        "runtime": {
            "pending_queue": {"pending_count": 0},
            "handoff_diagnostics": {"classification": "no_active_handoff"},
        },
    }


def main() -> int:
    checks: dict[str, bool] = {}
    evidence: dict[str, object] = {}

    with tempfile.TemporaryDirectory(prefix="ai-dev-244-registry-") as raw:
        root = Path(raw)
        rows = [
            entry("a_fast"),
            entry("b_timeout"),
            entry("post_merge_status", role="orchestrator"),
        ]
        registry = fixture_registry(root, rows)
        events: list[dict] = []

        def timeout_runner(path: Path) -> dict:
            if path.stem == "b_timeout":
                raise subprocess.TimeoutExpired(cmd=[sys.executable, str(path)], timeout=0.01, output="", stderr="fixture timeout")
            return {
                "returncode": 0,
                "stdout": json.dumps({"status": "PASS"}),
                "stderr": "",
                "duration_seconds": 0.0123,
            }

        timeout_gate = execute_validator_gate(
            "post_merge",
            caller_validator_id="post_merge_status",
            registry_path=registry,
            root=root,
            runner=timeout_runner,
            overall_timeout_seconds=5,
            progress_callback=events.append,
        )
        check("overall_timeout_fails_closed", timeout_gate["status"] == "FAIL" and timeout_gate["timed_out"] is True, checks)
        check("timeout_never_passes", timeout_gate["failed_count"] == 1 and timeout_gate["timeout"]["current_validator_id"] == "b_timeout", checks)
        check("completed_validator_timing_retained", timeout_gate["results"][0]["duration_seconds"] == 0.0123, checks)
        check("progress_available_before_gate_completion", any(event.get("event") == "validator_started" for event in events), checks)
        check("progress_reports_counts", any(event.get("total") == 3 for event in events if event.get("event") == "validator_started"), checks)

    with tempfile.TemporaryDirectory(prefix="ai-dev-244-registry-") as raw:
        root = Path(raw)
        rows = [entry("a_slow"), entry("b_fast"), entry("post_merge_status", role="orchestrator")]
        registry = fixture_registry(root, rows)

        def passing_runner(path: Path) -> dict:
            duration = 2.5 if path.stem == "a_slow" else 0.1
            return {
                "returncode": 0,
                "stdout": json.dumps({"status": "PASS"}),
                "stderr": "",
                "duration_seconds": duration,
            }

        pass_gate = execute_validator_gate(
            "post_merge",
            caller_validator_id="post_merge_status",
            registry_path=registry,
            root=root,
            runner=passing_runner,
            overall_timeout_seconds=10,
        )
        slow = slow_validator_summary(pass_gate, limit=1)
        check("successful_gate_still_passes", pass_gate["status"] == "PASS" and pass_gate["timed_out"] is False, checks)
        check("slow_validator_identity_reported", slow and slow[0]["validator_id"] == "a_slow", checks)

    dirty = classify_dirty_paths([
        "?? artifacts/runtime/delivery_receipts/tw/pre_open_0700/" + ("a" * 64) + ".json",
        " M app/runtime/validator_registry.py",
        "?? unexpected.txt",
    ])
    check("classifier_semantics_unchanged_preserved", len(dirty["preserved_runtime_artifacts"]) == 1, checks)
    check("classifier_semantics_unchanged_blocking", dirty["blocking_task_residue"] == ["app/runtime/validator_registry.py"], checks)
    check("classifier_semantics_unchanged_unknown", dirty["unknown_dirty_paths"] == ["unexpected.txt"], checks)

    post_merge = summarize_post_merge_status(clean_platform())
    check("final_success_json_contract_compatible", post_merge["ok"] is True and "checks" in post_merge and "git" in post_merge, checks)
    check("production_landing_contract_validator_exists", (ROOT / "scripts/orchestrator/validate_production_landing_integrity_v1.py").is_file(), checks)

    failures = [name for name, passed in checks.items() if not passed]
    evidence["timeout_gate"] = {
        "status": timeout_gate["status"],
        "timed_out": timeout_gate["timed_out"],
        "timeout": timeout_gate["timeout"],
        "completed_results": len(timeout_gate["results"]),
    }
    evidence["slow_validators"] = slow
    result = {
        "schema_version": "ai_dev_244_post_merge_validator_performance_timeout_reliability_v1",
        "task_id": "AI-DEV-244",
        "status": "PASS" if not failures else "FAIL",
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "checks": checks,
        "failures": failures,
        "evidence": evidence,
        "safety": {
            "production_mutation": False,
            "notifications": False,
            "db_sheet_write": False,
            "scheduler_or_infra_mutation": False,
            "trading": False,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
