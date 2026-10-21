from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from scripts.orchestrator.codex_full_batch_rerun import RerunRequest, load_input, run_isolated

class CodexFullRerunTests(unittest.TestCase):
    def request(self, root, mode="HISTORICAL_RECOMPUTE"):
        return RerunRequest(mode, "TW", "post_close_1500", "2026-10-20", root / "input.json", root / "out")
    def source(self, kind="CONTEMPORANEOUS_HISTORICAL"):
        return {"market":"TW","window":"post_close_1500","trading_date":"2026-10-20","source_kind":kind,"source_digest":"a"*64}
    def test_historical_runs_all_stages_with_isolated_receipt(self):
        with TemporaryDirectory() as raw:
            root=Path(raw); req=self.request(root); value=self.source(); req.input_source.write_text(json.dumps(value))
            source=load_input(req.input_source,req)
            receipt=run_isolated(req,source,lambda stage,_:{"status":"EXECUTED","stage_evidence":stage})
            self.assertEqual(receipt["terminal_status"],"SUCCESS")
            self.assertEqual(len(receipt["stages"]),7)
            self.assertTrue((req.output_dir/"execution_receipt.json").exists())
            self.assertFalse(receipt["notification_attempted"])
    def test_wrong_date_fails_before_stage_execution(self):
        with TemporaryDirectory() as raw:
            root=Path(raw); req=self.request(root); value=self.source(); value["trading_date"]="2026-10-19"; req.input_source.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,"TRADING_DATE"):
                load_input(req.input_source,req)
    def test_frozen_and_historical_contracts_are_not_interchangeable(self):
        with TemporaryDirectory() as raw:
            root=Path(raw); req=self.request(root,"FROZEN_REPLAY"); req.input_source.write_text(json.dumps(self.source()))
            with self.assertRaisesRegex(ValueError,"FROZEN"):
                load_input(req.input_source,req)
    def test_timeout_is_terminal_and_stops_later_stages(self):
        with TemporaryDirectory() as raw:
            root=Path(raw); req=self.request(root); value=self.source(); req.input_source.write_text(json.dumps(value)); source=load_input(req.input_source,req)
            receipt=run_isolated(req,source,lambda stage,_:{"status":"TIMEOUT","reason":"fixture"} if stage=="analysis_prediction" else {"status":"EXECUTED"})
            self.assertEqual(receipt["terminal_status"],"TIMEOUT")
            self.assertEqual([x["stage"] for x in receipt["stages"]],["market_data","analysis_prediction"])
    def test_live_requires_explicit_live_plan(self):
        with TemporaryDirectory() as raw:
            root=Path(raw); req=self.request(root,"LIVE_RERUN"); req.input_source.write_text(json.dumps(self.source()))
            with self.assertRaisesRegex(ValueError,"LIVE"):
                load_input(req.input_source,req)
if __name__=='__main__': unittest.main()
