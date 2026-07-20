from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.orchestrator.validate_post_merge_status import (
    classify_dirty_paths,
    collect_expanded_git_status,
    summarize_post_merge_status,
)


def platform(*, status: list[str] | None = None, sync: bool = True, branches: bool = False, open_prs: int = 0) -> dict:
    entries = list(status or [])
    return {
        "ok": True,
        "warnings": ["git working tree is not clean"] if entries else [],
        "open_pr_count": open_prs,
        "git": {
            "current_branch": "main",
            "clean": not entries,
            "status_short": entries,
            "main_origin_main_sync": {
                "status": "in_sync" if sync else "ahead",
                "ahead": 0 if sync else 1,
                "behind": 0,
            },
            "local_branches": ["main", "ai-dev/test"] if branches else ["main"],
            "remote_branches": ["origin/main", "origin/ai-dev/test"] if branches else ["origin/main"],
        },
        "runtime": {
            "pending_queue": {"pending_count": 0},
            "handoff_diagnostics": {"classification": "no_active_handoff"},
        },
    }


class PostMergeDirtyClassificationTests(unittest.TestCase):
    def test_clean_tree_passes(self) -> None:
        result = summarize_post_merge_status(platform())
        self.assertTrue(result["ok"])
        self.assertTrue(result["worktree_clean"])
        self.assertTrue(result["worktree_governance_safe"])

    def test_approved_artifacts_pass_with_warning(self) -> None:
        entries = [
            "M artifacts/runtime/formal_prediction_runtime_latest.json",
            "?? artifacts/runtime/delivery_provenance/tw_intraday_1305_email_latest.json",
            " M templates/multi_market_dashboard_v2/dashboard/archive/tw/intraday_1305/latest/index.html",
        ]
        result = summarize_post_merge_status(platform(status=entries))
        self.assertTrue(result["ok"])
        self.assertFalse(result["worktree_clean"])
        self.assertTrue(result["worktree_governance_safe"])
        self.assertEqual(len(result["preserved_runtime_artifacts"]), 3)
        self.assertTrue(result["warnings"])

    def test_modified_task_source_fails(self) -> None:
        result = summarize_post_merge_status(platform(status=[" M app/reports/example.py"]))
        self.assertFalse(result["ok"])
        self.assertEqual(result["blocking_task_residue"], ["app/reports/example.py"])

    def test_untracked_source_fails(self) -> None:
        result = summarize_post_merge_status(platform(status=["?? scripts/orchestrator/new_validator.py"]))
        self.assertFalse(result["ok"])
        self.assertEqual(result["blocking_task_residue"], ["scripts/orchestrator/new_validator.py"])

    def test_unknown_root_file_fails_closed(self) -> None:
        result = summarize_post_merge_status(platform(status=["?? mystery-output.json"]))
        self.assertFalse(result["ok"])
        self.assertEqual(result["unknown_dirty_paths"], ["mystery-output.json"])

    def test_artifact_plus_source_fails(self) -> None:
        result = summarize_post_merge_status(platform(status=[
            " M artifacts/runtime/formal_prediction_runtime_latest.json", " M docs/runbooks/task.md",
        ]))
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["preserved_runtime_artifacts"]), 1)
        self.assertEqual(result["blocking_task_residue"], ["docs/runbooks/task.md"])

    def test_main_mismatch_fails(self) -> None:
        result = summarize_post_merge_status(platform(sync=False))
        self.assertFalse(result["ok"])
        self.assertFalse(result["main_sync_ok"])

    def test_open_pr_or_branch_cleanup_fails(self) -> None:
        self.assertFalse(summarize_post_merge_status(platform(branches=True))["ok"])
        self.assertFalse(summarize_post_merge_status(platform(open_prs=1))["ok"])

    def test_arbitrary_generated_looking_path_fails(self) -> None:
        entries = [
            "?? artifacts/runtime/generated-looking/random.json",
            "?? artifacts/runtime/delivery_provenance/arbitrary.json",
            "?? artifacts/runtime/delivery_provenance/us_pre_open_0700_email_latest.json",
        ]
        paths = classify_dirty_paths(entries)
        self.assertEqual(paths["unknown_dirty_paths"], sorted(entry[3:] for entry in entries))
        self.assertFalse(summarize_post_merge_status(platform(status=entries))["ok"])

    def test_evaluation_does_not_mutate_input(self) -> None:
        source = platform(status=[" M artifacts/runtime/formal_prediction_runtime_latest.json"])
        before = copy.deepcopy(source)
        summarize_post_merge_status(source)
        self.assertEqual(source, before)

    def test_status_collection_does_not_mutate_worktree_or_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            tracked = repo / "tracked.txt"
            tracked.write_text("before\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
            tracked.write_text("after\n", encoding="utf-8")
            (repo / "untracked.txt").write_text("keep\n", encoding="utf-8")
            before = subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=repo, check=True, capture_output=True, text=True,
            ).stdout

            entries, error = collect_expanded_git_status(repo)

            after = subprocess.run(
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                cwd=repo, check=True, capture_output=True, text=True,
            ).stdout
            self.assertIsNone(error)
            self.assertTrue(entries)
            self.assertEqual(before, after)
            self.assertEqual(tracked.read_text(encoding="utf-8"), "after\n")
            self.assertEqual((repo / "untracked.txt").read_text(encoding="utf-8"), "keep\n")


if __name__ == "__main__":
    unittest.main()
