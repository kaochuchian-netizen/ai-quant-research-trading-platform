"""AI-DEV-300: scheduled orchestrator cannot mutate checked-out source.

This suite inspects the installer-generated wrapper WITHOUT running the
installer, systemd, production batches, Git remotes, or notifications.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts/orchestrator/bootstrap_timer_pull_loop.sh"
RUNNER = ROOT / "scripts/orchestrator/run_loop_once.py"


def generated_wrapper() -> str:
    script = BOOTSTRAP.read_text(encoding="utf-8")
    match = re.search(
        r"cat > \"\$HOME/\.local/bin/stock-ai-orchestrator-loop\.sh\" << 'EOF'\n(.*?)\nEOF",
        script,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("WRAPPER_HEREDOC_MISSING")
    return match.group(1) + "\n"


class AutoSyncGovernanceTest(unittest.TestCase):
    def test_generated_wrapper_is_valid_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wrapper.sh"
            path.write_text(generated_wrapper(), encoding="utf-8")
            subprocess.run(["bash", "-n", str(path)], check=True, capture_output=True, text=True)

    def test_wrapper_executes_only_the_local_loop(self) -> None:
        wrapper = generated_wrapper()
        # A timer-driven wrapper is never an approved deployment entrypoint.
        unsafe = (
            r"\bgit\s+(?:-\S+\s+)*(?:pull|fetch|reset|checkout|switch|merge|rebase|push)\b",
            r"\bgit\s+.*\b(?:update-ref|read-tree)\b",
            r"\b(?:sudo|systemctl|docker)\s+.*\b(?:restart|start|enable|reload)\b",
        )
        shell_commands = "\n".join(line for line in wrapper.splitlines()
                                   if line.strip() and not line.lstrip().startswith("#"))
        for pattern in unsafe:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, shell_commands), "AUTO_SOURCE_MUTATION_FORBIDDEN")
        self.assertIn("run_loop_once.py", shell_commands)
        self.assertIn("--check-remote", shell_commands)

    def test_runner_remote_probe_is_not_a_pull(self) -> None:
        runner = RUNNER.read_text(encoding="utf-8")
        self.assertIn('["git", "fetch", "--dry-run", remote]', runner)
        self.assertNotIn('["git", "pull"', runner)
        self.assertNotIn('["git", "reset"', runner)

    def test_bootstrap_never_installs_pull_before_a_governance_gate(self) -> None:
        source = BOOTSTRAP.read_text(encoding="utf-8")
        wrapper = generated_wrapper()
        self.assertNotIn("git pull --ff-only", wrapper)
        self.assertTrue(source.index("cat >") < source.index("systemctl --user"))
        self.assertIn("set -euo pipefail", wrapper)


if __name__ == "__main__":
    unittest.main()
