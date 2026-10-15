from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from app.pipelines import afternoon_report_pipeline as pipeline
from app.runtime.stage_timing import StageTimingRecorder, TW_INTRADAY_1305_BUDGET


class Tw1500IntradayLifecycleTests(unittest.TestCase):
    def test_optional_intraday_archive_success_records_terminal_completed_stage(self) -> None:
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        evidence = {"2330": {"evidence_status": "OBSERVED"}}
        manifest = {"content_hash": "a" * 64}
        calls: list[tuple[tuple, dict]] = []

        with patch.object(pipeline, "_post_close_intraday_evidence", return_value=(evidence, manifest)), patch.object(
            pipeline, "record_stage_result", side_effect=lambda *args, **kwargs: calls.append((args, kwargs))
        ):
            actual_evidence, actual_manifest = pipeline._collect_optional_post_close_intraday_evidence(
                timing_path=tmp_path / "timing.json", trading_session="2026-10-15"
            )

        self.assertEqual((actual_evidence, actual_manifest), (evidence, manifest))
        self.assertEqual(calls, [
            ((tmp_path / "timing.json", "intraday_archive"), {"status": "completed", "elapsed_seconds": 0})
        ])


    def test_optional_intraday_archive_failure_is_terminal_optional_stage_not_pipeline_error(self) -> None:
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        calls: list[tuple[tuple, dict]] = []

        with patch.object(pipeline, "_post_close_intraday_evidence", side_effect=ValueError("collector failed")), patch.object(
            pipeline, "record_stage_result", side_effect=lambda *args, **kwargs: calls.append((args, kwargs))
        ):
            evidence, manifest = pipeline._collect_optional_post_close_intraday_evidence(
                timing_path=tmp_path / "timing.json", trading_session="2026-10-15"
            )

        self.assertEqual(evidence, {})
        self.assertIsNone(manifest)
        self.assertEqual(calls, [
            (
                (tmp_path / "timing.json", "intraday_archive"),
                {
                    "status": "failed_optional",
                    "elapsed_seconds": 0,
                    "error_category": "pipeline_failure",
                    "error_message_sanitized": "ValueError",
                },
            )
        ])

    def test_collector_exception_persists_failed_optional_stage_without_raising(self) -> None:
        tmp_path = Path(self.enterContext(TemporaryDirectory()))
        timing_path = tmp_path / "timing.json"
        StageTimingRecorder(
            timing_path,
            market="TW",
            window="post_close_1500",
            run_id="fixture-run",
            budget=TW_INTRADAY_1305_BUDGET,
        )

        with patch.object(pipeline, "_post_close_intraday_evidence", side_effect=RuntimeError("network unavailable")):
            evidence, manifest = pipeline._collect_optional_post_close_intraday_evidence(
                timing_path=timing_path, trading_session="2026-10-15"
            )

        receipt = json.loads(timing_path.read_text(encoding="utf-8"))
        self.assertEqual((evidence, manifest), ({}, None))
        self.assertEqual(receipt["status"], "running")
        self.assertEqual(receipt["stages"][-1]["stage"], "intraday_archive")
        self.assertEqual(receipt["stages"][-1]["status"], "failed_optional")
        self.assertEqual(receipt["stages"][-1]["error_message_sanitized"], "RuntimeError")


    def test_optional_failure_uses_only_record_stage_result_contract_keywords(self) -> None:
        source = Path(pipeline.__file__).read_text(encoding="utf-8")
        helper = source[source.index("def _collect_optional_post_close_intraday_evidence"):source.index("def run_afternoon_report_pipeline")]
        self.assertNotIn("manifest_digest=", helper)
        self.assertNotIn("reason=", helper)
        self.assertIn("error_message_sanitized=", helper)
