"""AI-DEV-279 timeout isolation and terminal-status regression tests."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.runtime.validator_registry import evaluate_validator_entry, execute_validator_gate


def entry(validator_id: str, *, critical: bool = False) -> dict:
    return {
        "validator_id": validator_id,
        "path": f"validators/{validator_id}.py",
        "status": "ACTIVE",
        "execution_role": "leaf",
        "scope": "fixture",
        "introduced_by": "AI-DEV-279",
        "reason": "fixture",
        "required_in_branch_gate": True,
        "required_in_post_merge": True,
        "last_contract_version": "fixture_v1",
        "timeout_impact": "critical" if critical else "noncritical",
    }


def registry(root: Path, rows: list[dict]) -> Path:
    for row in rows:
        target = root / row["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# fixture\n", encoding="utf-8")
    target = root / "registry.json"
    target.write_text(json.dumps({"schema_version": "validator_registry_v2", "version": "fixture", "validators": rows}), encoding="utf-8")
    return target


class ValidatorTimeoutIsolationTests(unittest.TestCase):
    def test_terminal_statuses_are_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            row = entry("probe")
            reg = registry(root, [row])
            self.assertTrue(reg.is_file())

            def pass_runner(_: Path) -> dict:
                return {"returncode": 0, "stdout": '{"status":"PASS"}', "stderr": ""}

            def fail_runner(_: Path) -> dict:
                return {"returncode": 2, "stdout": "", "stderr": "failed"}

            def timeout_runner(path: Path) -> dict:
                raise subprocess.TimeoutExpired([sys.executable, str(path)], 1, output="progress=acquired", stderr="")

            def error_runner(_: Path) -> dict:
                raise RuntimeError("fixture")

            target = root / row["path"]
            self.assertEqual(evaluate_validator_entry(row, pass_runner, root=root)["execution_status"], "PASS")
            self.assertEqual(evaluate_validator_entry(row, fail_runner, root=root)["execution_status"], "FAIL")
            self.assertEqual(evaluate_validator_entry(row, timeout_runner, root=root)["execution_status"], "TIMEOUT")
            self.assertEqual(evaluate_validator_entry(row, error_runner, root=root)["execution_status"], "ERROR")
            self.assertTrue(target.is_file())

    def test_timeout_keeps_following_validator_and_applies_scope_policy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            reg = registry(root, [entry("a_timeout"), entry("b_after"), entry("production_landing_integrity", critical=True)])

            def runner(path: Path) -> dict:
                if path.stem in {"a_timeout", "production_landing_integrity"}:
                    raise subprocess.TimeoutExpired([sys.executable, str(path)], 1, output="progress=started", stderr="")
                return {"returncode": 0, "stdout": '{"status":"PASS"}', "stderr": ""}

            gate = execute_validator_gate("branch", caller_validator_id="branch_gate", registry_path=reg, root=root, runner=runner)
            by_id = {result["validator_id"]: result for result in gate["results"]}
            self.assertEqual(by_id["a_timeout"]["execution_status"], "TIMEOUT")
            self.assertEqual(by_id["b_after"]["execution_status"], "PASS")
            self.assertEqual(gate["status"], "TIMEOUT")
            self.assertEqual(gate["validator_status_counts"]["TIMEOUT"], 2)
            self.assertEqual(gate["deployment_impact"]["status"], "BLOCKED")
            self.assertIn("production_landing_integrity", gate["deployment_impact"]["critical_timeout_validator_ids"])

    def test_noncritical_timeout_requires_approval_without_becoming_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            reg = registry(root, [entry("a_timeout"), entry("b_after")])

            def runner(path: Path) -> dict:
                if path.stem == "a_timeout":
                    raise subprocess.TimeoutExpired([sys.executable, str(path)], 1, output="progress=started", stderr="")
                return {"returncode": 0, "stdout": '{"status":"PASS"}', "stderr": ""}

            gate = execute_validator_gate("branch", caller_validator_id="branch_gate", registry_path=reg, root=root, runner=runner)
            self.assertEqual(gate["status"], "TIMEOUT")
            self.assertEqual(gate["deployment_impact"]["status"], "PENDING_APPROVAL")
            self.assertEqual(gate["failed_count"], 0)
            self.assertEqual(gate["timeout_count"], 1)
            timeout_row = next(row for row in gate["results"] if row["validator_id"] == "a_timeout")
            self.assertEqual(timeout_row["last_progress"], "progress=started")
            self.assertIsNotNone(timeout_row["started_at"])
            self.assertIsNotNone(timeout_row["finished_at"])

    def test_unstarted_validator_is_pending_not_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            reg = registry(root, [entry("a"), entry("b")])
            gate = execute_validator_gate(
                "branch", caller_validator_id="branch_gate", registry_path=reg, root=root,
                runner=lambda _: {"returncode": 0, "stdout": '{"status":"PASS"}', "stderr": ""},
                overall_timeout_seconds=0,
            )
            self.assertEqual(gate["status"], "PENDING")
            self.assertEqual(gate["timeout_count"], 0)
            self.assertEqual(gate["pending_count"], 2)
            self.assertEqual(gate["deployment_impact"]["status"], "PENDING_APPROVAL")

    def test_timeout_cleanup_terminates_only_owned_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            row = entry("hang")
            registry(root, [row])
            pid_file = root / "child.pid"
            target = root / row["path"]
            target.write_text(
                "import subprocess, sys, time\n"
                f"child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                f"open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
                "print('progress=child-started', flush=True)\n"
                "time.sleep(60)\n",
                encoding="utf-8",
            )
            result = evaluate_validator_entry(row, root=root, timeout_seconds=1)
            self.assertEqual(result["execution_status"], "TIMEOUT")
            self.assertIn(result["cleanup_action"], {"SIGTERM", "SIGKILL", "ALREADY_EXITED"})
            self.assertEqual(result["last_progress"], "progress=child-started")
            child_pid = int(pid_file.read_text(encoding="utf-8"))
            for _ in range(20):
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            else:
                self.fail("owned descendant remained after timeout cleanup")


if __name__ == "__main__":
    unittest.main()
