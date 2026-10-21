from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.orchestrator.codex_full_batch_rerun import RerunRequest, STAGES, load_input, run_isolated


class CodexFullBatchRerunTests(unittest.TestCase):
    def request(self, root: Path) -> RerunRequest:
        return RerunRequest("HISTORICAL_RECOMPUTE", "TW", "post_close_1500", "2026-10-20", root / "input.json", root / "out")

    def source(self, *, timeout: bool = False) -> dict[str, object]:
        stages = {
            stage: {
                "kind": "isolated_adapter",
                "isolation_contract": "ISOLATED_STAGE_ADAPTER_V1",
                "command": [sys.executable, "-c", "from pathlib import Path; import os; " f"Path(os.environ['STOCK_AI_RERUN_OUTPUT_DIR']).joinpath('{stage}.json').write_text('{{}}')"],
                "expected_output": f"{stage}.json",
            }
            for stage in STAGES
        }
        if timeout:
            stages["analysis_prediction"] = {"kind": "isolated_adapter", "isolation_contract": "ISOLATED_STAGE_ADAPTER_V1", "command": [sys.executable, "-c", "import time; time.sleep(1)"], "expected_output": "never.json", "timeout_seconds": 1}
        return {"market": "TW", "window": "post_close_1500", "trading_date": "2026-10-20", "source_kind": "CONTEMPORANEOUS_HISTORICAL", "source_digest": "a" * 64, "stages": stages}

    def test_declared_isolated_adapter_execution_is_evidenced(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp); request = self.request(root); request.input_source.write_text(json.dumps(self.source()))
            result = run_isolated(request, load_input(request.input_source, request))
            self.assertEqual(result["terminal_status"], "SUCCESS")
            self.assertTrue(all(row["status"] == "EXECUTED" for row in result["stages"]))
            self.assertTrue((request.output_dir / "execution_receipt.json").is_file())

    def test_missing_adapter_fails_closed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp); request = self.request(root); source = self.source(); source["stages"]["market_data"] = {}; request.input_source.write_text(json.dumps(source))
            result = run_isolated(request, load_input(request.input_source, request))
            self.assertEqual(result["terminal_status"], "FAILED")
            self.assertEqual(result["stages"][0]["reason"], "ISOLATED_STAGE_ADAPTER_REQUIRED")

    def test_official_pipeline_is_explicitly_blocked_without_isolation_contract(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp); request = self.request(root); source = self.source(); source["stages"]["market_data"] = {"kind": "official_pipeline"}; request.input_source.write_text(json.dumps(source))
            result = run_isolated(request, load_input(request.input_source, request))
            self.assertEqual(result["terminal_status"], "BLOCKED")
            self.assertEqual(result["stages"][0]["reason"], "OFFICIAL_PIPELINE_ISOLATION_UNSUPPORTED")

    def test_wrong_date_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp); request = self.request(root); source = self.source(); source["trading_date"] = "bad"; request.input_source.write_text(json.dumps(source))
            with self.assertRaises(ValueError): load_input(request.input_source, request)

    def test_timeout_has_terminal_receipt(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp); request = self.request(root); request.input_source.write_text(json.dumps(self.source(timeout=True)))
            result = run_isolated(request, load_input(request.input_source, request))
            self.assertEqual(result["terminal_status"], "TIMEOUT")
            self.assertEqual(result["stages"][1]["status"], "TIMEOUT")


if __name__ == "__main__":
    unittest.main()
