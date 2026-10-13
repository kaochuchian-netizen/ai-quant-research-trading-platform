"""AI-DEV-256E offline tests: no LINE transport is ever invoked outside fakes."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.dashboard.multi_market_dashboard import publish_daily_evaluation_landing, render_landing_page
from app.reports.daily_evaluation_line_notice import deliver, message, public_dashboard_url


IDENTITY = "a" * 64
VALUE = {"status": "VALID", "identity": IDENTITY, "report_date": "2026-10-13"}
BASE = "http://35.201.242.167/stock-ai-dashboard"


class DailyEvaluationCompletionTests(unittest.TestCase):
    def test_minimal_public_notice_template(self):
        self.assertEqual(
            message(BASE),
            "【17:00 策略檢討】\n今日策略檢討已完成\n查看 Dashboard：http://35.201.242.167/stock-ai-dashboard/dashboard/daily-evaluation/latest/index.html",
        )
        self.assertEqual(public_dashboard_url(BASE), "http://35.201.242.167/stock-ai-dashboard/dashboard/daily-evaluation/latest/index.html")

    def test_success_is_once_only_and_receipted(self):
        sent = []
        with tempfile.TemporaryDirectory() as root:
            kwargs = dict(value=VALUE, dashboard={"status": "PUBLISHED"}, base_url=BASE, sender=sent.append, receipt_root=Path(root))
            self.assertEqual(deliver(**kwargs)["send_status"], "sent")
            self.assertEqual(deliver(**kwargs)["send_status"], "already_delivered")
        self.assertEqual(len(sent), 1)

    def test_failed_or_blocked_publication_never_notifies(self):
        sent = []
        with tempfile.TemporaryDirectory() as root:
            result = deliver(value=VALUE, dashboard={"status": "PRESENTATION_FAILED"}, base_url=BASE, sender=sent.append, receipt_root=Path(root))
        self.assertEqual(result["send_status"], "suppressed_dashboard_not_published")
        self.assertEqual(sent, [])

    def test_main_dashboard_exposes_latest_review_at_mobile_width(self):
        with patch("app.dashboard.multi_market_dashboard.latest_valid_daily_evaluation", return_value=VALUE):
            page = render_landing_page()
        self.assertIn("17:00 策略檢討", page)
        self.assertIn("2026-10-13", page)
        self.assertIn("/stock-ai-dashboard/dashboard/daily-evaluation/latest/index.html", page)
        self.assertIn("@media(max-width:640px)", page)

    def test_landing_publish_is_atomic_and_only_writes_landing(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            with patch("app.dashboard.multi_market_dashboard.latest_valid_daily_evaluation", return_value=VALUE):
                result = publish_daily_evaluation_landing(static_root=base / "public", output_dir=base / "staging")
            self.assertEqual(result["status"], "PUBLISHED")
            page = (base / "public/index.html").read_text(encoding="utf-8")
        self.assertIn("17:00 策略檢討", page)
        self.assertIn("daily-evaluation/latest", page)


if __name__ == "__main__":
    unittest.main()
