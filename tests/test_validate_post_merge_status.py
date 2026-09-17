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
            "head_sha": "abc123",
            "main_sha": "abc123",
            "origin_main_sha": "abc123",
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
            "?? artifacts/runtime/manual_rerun/manual_rerun_manual-d1ce592d91f9b066.json",
            " M templates/multi_market_dashboard_v2/dashboard/archive/tw/intraday_1305/latest/index.html",
        ]
        result = summarize_post_merge_status(platform(status=entries))
        self.assertTrue(result["ok"])
        self.assertFalse(result["worktree_clean"])
        self.assertTrue(result["worktree_governance_safe"])
        self.assertEqual(len(result["preserved_runtime_artifacts"]), 4)
        self.assertTrue(result["warnings"])

    def test_tw_ledger_and_manual_progress_are_preserved(self) -> None:
        entries = [
            "?? artifacts/runtime/tw/evidence_regression_ledger/v1/2026-08-31/pre_open_0700/2330/tw_ledger_eca6959dcf8710957ad28f10bf34.json",
            "?? artifacts/runtime/tw/evidence_regression_ledger/v1/2026-09-17/pre_open_0700/009816/tw_ledger_0123456789abcdef0123456789ab.json",
            "?? artifacts/runtime/manual_rerun/progress/manual-5857673720edd692.jsonl",
            "?? artifacts/runtime/manual_rerun/progress/manual-6e41610311625470.jsonl",
        ]
        result = summarize_post_merge_status(platform(status=entries))
        self.assertTrue(result["ok"])
        self.assertEqual(result["preserved_runtime_artifacts"], sorted(entry[3:] for entry in entries))
        self.assertEqual(result["unknown_dirty_paths"], [])

    def test_tw_preopen_hashed_delivery_receipt_is_preserved(self) -> None:
        path = "artifacts/runtime/delivery_receipts/tw/pre_open_0700/" + ("a" * 64) + ".json"
        result = summarize_post_merge_status(platform(status=[f"?? {path}"]))
        self.assertTrue(result["ok"])
        self.assertEqual(result["preserved_runtime_artifacts"], [path])
        self.assertEqual(result["unknown_dirty_paths"], [])

    def test_tw_preopen_delivery_receipt_similar_paths_remain_blocked(self) -> None:
        entries = [
            "?? artifacts/runtime/delivery_receipts/tw/pre_open_0700/arbitrary.json",
            "?? artifacts/runtime/delivery_receipts/tw/pre_open_0700/" + ("a" * 63) + ".json",
            "?? artifacts/runtime/delivery_receipts/tw/pre_open_0700/" + ("a" * 64) + ".jsonl",
            "?? artifacts/runtime/delivery_receipts/tw/pre_open_0700/archive/" + ("a" * 64) + ".json",
            "?? artifacts/runtime/delivery_receipts/tw/intraday_1305/" + ("a" * 64) + ".json",
            "?? artifacts/runtime/delivery_receipts/us/pre_open_0700/" + ("a" * 64) + ".json",
            "?? stock-ai-key.json.pre-migration-20260911",
            " M app/reports/tw_pre_open_delivery_contract.py",
        ]
        result = summarize_post_merge_status(platform(status=entries))
        self.assertFalse(result["ok"])
        self.assertEqual(result["preserved_runtime_artifacts"], [])
        self.assertEqual(result["blocking_task_residue"], ["app/reports/tw_pre_open_delivery_contract.py"])
        self.assertEqual(result["unknown_dirty_paths"], sorted(entry[3:] for entry in entries[:-1]))

    def test_similar_paths_and_credential_backup_remain_blocked(self) -> None:
        entries = [
            "?? artifacts/runtime/tw/evidence_regression_ledger/v1/2026-08-31/pre_open_0700/2330/arbitrary.json",
            "?? artifacts/runtime/tw/evidence_regression_ledger/v1/2026-08-31/not_a_window/2330/tw_ledger_eca6959dcf8710957ad28f10bf34.json",
            "?? artifacts/runtime/manual_rerun/progress/random.jsonl",
            "?? artifacts/runtime/manual_rerun/progress/manual-5857673720edd692.jsonl.bak",
            "?? stock-ai-key.json.pre-migration-20260911",
            " M app/reports/tw_evidence_regression.py",
        ]
        result = summarize_post_merge_status(platform(status=entries))
        self.assertFalse(result["ok"])
        self.assertEqual(result["blocking_task_residue"], ["app/reports/tw_evidence_regression.py"])
        self.assertEqual(result["unknown_dirty_paths"], sorted(entry[3:] for entry in entries[:-1]))
        self.assertEqual(result["preserved_runtime_artifacts"], [])

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

    def test_stale_feature_checkout_fails_even_when_main_is_synced(self) -> None:
        source = platform()
        source["git"].update(current_branch="ai-dev/228-test", head_sha="feature123")
        result = summarize_post_merge_status(source)
        self.assertFalse(result["ok"])
        self.assertEqual(result["production_checkout_status"], "NOT_CLOSED")
        self.assertFalse(result["checks"]["production_checkout_identity_closed"]["passed"])

    def test_head_main_origin_identity_mismatch_fails(self) -> None:
        source = platform()
        source["git"]["head_sha"] = "stale123"
        result = summarize_post_merge_status(source)
        self.assertFalse(result["ok"])
        self.assertFalse(result["checks"]["production_checkout_identity_closed"]["passed"])

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
