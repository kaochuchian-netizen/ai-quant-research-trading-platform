"""AI-DEV-256C presentation tests; synthetic evaluator results only."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.dashboard.daily_learning_presentation import publish_dashboard, render_dashboard, render_line_summary
from app.evaluation.daily_evaluation import build_daily
from test_daily_evaluation import mature_inputs


def reviewed_value():
    value = build_daily("2026-09-25", mature_inputs())
    for market in ("TW", "US"):
        value["learning_artifact"]["markets"][market] = {
            "finding": "DIRECTION_ERROR_OBSERVED",
            "actionable_learning": {
                "id": "AVOID_REPEATING_MATURE_DIRECTION_ERROR",
                "active": True,
                "avoid_directions": ["UP"],
            },
        }
    return value


class DailyLearningPresentationTests(unittest.TestCase):
    def test_mobile_dashboard_is_zh_tw_and_hides_internal_values(self):
        page = render_dashboard(reviewed_value())
        for heading in ("【每日策略檢討】", "台股", "美股", "預測成果", "策略檢討", "學習調整", "今日結論", "下一交易日調整", "詳細評估資料"):
            self.assertIn(heading, page)
        self.assertIn("@media(max-width:393px)", page)
        self.assertIn("今日部分方向判斷與實際走勢不一致", page)
        for forbidden in ("DIRECTION_ERROR_OBSERVED", "AVOID_REPEATING_MATURE_DIRECTION_ERROR", "content_hash", "FROZEN_REPLAY"):
            self.assertNotIn(forbidden, page)

    def test_line_formatter_uses_the_same_evaluation_source_without_sending(self):
        summary = render_line_summary(reviewed_value())
        self.assertIn("【每日策略檢討】", summary)
        self.assertIn("台股", summary)
        self.assertIn("美股", summary)
        self.assertNotIn("DIRECTION_ERROR_OBSERVED", summary)
        self.assertNotIn("content_hash", summary)

    def test_dashboard_publish_is_an_atomic_static_sidecar(self):
        value = reviewed_value()
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            result = publish_dashboard(value, static_root=base / "public", output_root=base / "staging")
            self.assertEqual(result["status"], "PUBLISHED")
            self.assertTrue((base / "public/dashboard/daily-evaluation/latest/index.html").is_file())
            self.assertTrue((base / "public/dashboard/daily-evaluation/2026-09-25" / value["identity"] / "index.html").is_file())
            self.assertIn("每日策略檢討", (base / "public/dashboard/daily-evaluation/latest/index.html").read_text())

    def test_invalid_identity_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "DAILY_PRESENTATION_IDENTITY"):
                publish_dashboard({}, static_root=Path(root) / "public", output_root=Path(root) / "staging")


if __name__ == "__main__":
    unittest.main()
