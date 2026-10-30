"""US delivery failure evidence regression; no real transports or credentials."""
import argparse
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.orchestrator import approved_us_stock_delivery as delivery


class WorkerEvidenceTests(unittest.TestCase):
    def args(self):
        return argparse.Namespace(window="us_pre_market_2000", timeout_seconds=None,
                                  live_data=False, publish_dashboard=False, pretty=False,
                                  as_of=None, manual_rerun=False)

    def payload(self):
        return {"ok": False, "status": {
            "schema_version": "us_stock_delivery_status_v1", "market": "US",
            "window": "us_pre_market_2000", "status": "completed",
            "delivery_status": "partial_failure", "email_attempted": True,
            "email_succeeded": True, "line_attempted": True, "line_succeeded": False,
        }, "email": {"attempted": True, "succeeded": True, "receipt_path": "email.json"},
            "line": {"attempted": True, "succeeded": False, "receipt_path": "line.json"}}

    def supervise(self, payload, code=2):
        process = subprocess.CompletedProcess([], code, json.dumps(payload), "benign warning")
        with patch.object(delivery.subprocess, "run", return_value=process), \
             patch.object(delivery, "_persist_reliability_failure") as persist:
            result = delivery.supervise_production_worker(self.args())
        return result, persist

    def test_partial_delivery_keeps_both_channel_facts(self):
        result, persist = self.supervise(self.payload())
        self.assertFalse(result["ok"])
        self.assertTrue(result["status"]["email_succeeded"])
        self.assertTrue(result["status"]["line_attempted"])
        self.assertEqual(result["line"]["receipt_path"], "line.json")
        self.assertEqual(result["worker"]["returncode"], 2)
        persist.assert_not_called()

    def test_missing_wrong_window_or_inconsistent_evidence_fails_closed(self):
        for kind in ("missing", "window", "inconsistent", "signal", "nonobject"):
            with self.subTest(kind=kind):
                payload = self.payload()
                if kind == "missing": payload.pop("email")
                if kind == "window": payload["status"]["window"] = "us_intraday_2300"
                if kind == "inconsistent": payload["status"]["email_attempted"] = False
                if kind == "nonobject": payload = []
                result, persist = self.supervise(payload, -9 if kind == "signal" else 2)
                self.assertFalse(result["ok"])
                persist.assert_called_once()


class ReceiptEvidenceTests(unittest.TestCase):
    def test_http_failure_is_masked_preserved_and_never_retried(self):
        snapshot = {"market": "US", "window": "us_pre_market_2000",
                    "effective_trading_date": "2026-10-30", "revision": 1,
                    "snapshot_id": "synthetic-291", "payload": {"synthetic": True}}
        private = "synthetic-private-recipient"
        error = Exception(f"LINE push failed for {private}: 429 "
                          '{"message":"You have reached your monthly limit."}')
        with tempfile.TemporaryDirectory() as tmp, \
             patch("dotenv.load_dotenv", return_value=False), \
             patch("reports.line_report_sender.get_line_user_ids", return_value=[private]), \
             patch("reports.line_report_sender.send_line_report", side_effect=error) as sender, \
             patch.object(delivery, "line_text", return_value="synthetic report"):
            first = delivery.send_us_channel_with_receipt({}, "us_pre_market_2000", "line", snapshot, Path(tmp))
            second = delivery.send_us_channel_with_receipt({}, "us_pre_market_2000", "line", snapshot, Path(tmp))
            self.assertEqual(sender.call_count, 1)
            self.assertFalse(first["succeeded"])
            self.assertFalse(second["attempted"])
            chunk = first["receipt"]["chunk_delivery"]
            self.assertEqual(chunk["http_status"], 429)
            self.assertEqual(chunk["provider_reason"], "monthly_limit_reached")
            self.assertEqual(chunk["completed_chunk_count"], 0)
            raw = Path(first["receipt_path"]).read_text()
            self.assertNotIn(private, raw)
            self.assertNotIn("You have reached", raw)

    def test_unknown_exception_does_not_invent_http_or_leak_text(self):
        with patch("dotenv.load_dotenv", return_value=False), \
             patch("reports.line_report_sender.get_line_user_ids", return_value=["synthetic"]), \
             patch("reports.line_report_sender.send_line_report", side_effect=Exception("private diagnostic")), \
             patch.object(delivery, "line_text", return_value="synthetic report"):
            result = delivery.send_line_if_allowed({}, "us_pre_market_2000", True)
        self.assertNotIn("http_status", result["chunk_delivery"])
        self.assertNotIn("private diagnostic", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
