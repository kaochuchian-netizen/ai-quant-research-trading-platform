from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from app.reports.mobile_decision_presentation import project_payload, render_line
from app.reports.post_close_quality_gate import batch_gate, evaluate_card
from app.reports.tw_tactical_direction_evaluation import project_tactical_direction_evaluation

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "ai_dev_275_tw_20261016_golden.json").read_text())
URL = "https://dashboard.example.test/stock-ai-dashboard/dashboard/tw/post-close/latest/"


class TwTacticalPresentationParityTests(unittest.TestCase):
    def setUp(self):
        self.cards = deepcopy(FIXTURE["structured_review_cards"])

    def test_real_immutable_snapshot_has_canonical_per_symbol_results(self):
        projected = [evaluate_card(card, market="TW", window="post_close_1500") for card in self.cards]
        self.assertEqual(sum(row["direction"]["result"] == "hit" for row in projected), 5)
        self.assertEqual(sum(row["direction"]["result"] == "miss" for row in projected), 3)
        self.assertEqual(sum(row["direction"]["result"] == "not_applicable" for row in projected), 2)
        self.assertEqual(sum(row["range"]["result"] == "hit" for row in projected), 1)
        self.assertEqual(sum(row["range"]["result"] == "partial_hit" for row in projected), 7)
        self.assertEqual(sum(row["range"]["result"] == "not_applicable" for row in projected), 2)
        rows = {row["symbol"]: row for row in projected}
        self.assertEqual(rows["009816"]["range"]["result"], "hit")
        self.assertEqual(rows["6873"]["direction"]["status"], "NOT_APPLICABLE")
        self.assertEqual(rows["3293"]["range"]["status"], "NOT_APPLICABLE")

    def test_projection_uses_frozen_tactical_identity_not_research_v2(self):
        card = deepcopy(self.cards[1])
        card["prediction_evaluation_v2"] = {"direction": {"forecast": "bearish", "actual": "bearish", "hit": True}}
        projected = project_tactical_direction_evaluation(card)
        self.assertEqual(projected["forecast"], "neutral")
        self.assertEqual(projected["actual"], "bearish")
        self.assertEqual(projected["result"], "hit")
        self.assertEqual(projected["scope"], "TW_FROZEN_TACTICAL_DIRECTION")

    def test_missing_evidence_and_identity_mismatch_fail_closed(self):
        missing = deepcopy(self.cards[0]); missing.pop("direction_hit")
        self.assertEqual(evaluate_card(missing, market="TW", window="post_close_1500")["direction"]["reason_code"], "TACTICAL_DIRECTION_RESULT_MISSING")
        mismatch = deepcopy(self.cards[0]); mismatch["prediction_snapshot_id"] = "other"
        self.assertEqual(evaluate_card(mismatch, market="TW", window="post_close_1500")["direction"]["reason_code"], "TACTICAL_FROZEN_IDENTITY_MISMATCH")

    def test_invalid_interval_is_not_silently_repaired(self):
        card = deepcopy(self.cards[2])
        card["prediction_interval_integrity"] = {"status": "INVALID"}
        card["prediction_range_result"] = "hit"
        result = evaluate_card(card, market="TW", window="post_close_1500")
        self.assertIsNone(result["range"]["result"])
        self.assertEqual(result["range"]["reason_code"], "PREDICTION_INTERVAL_INVALID")

    def test_partial_hit_and_miss_are_admitted(self):
        partial = evaluate_card(self.cards[0], market="TW", window="post_close_1500")
        miss = evaluate_card({**self.cards[0], "prediction_range_result": "miss"}, market="TW", window="post_close_1500")
        self.assertEqual(partial["range"]["result"], "partial_hit")
        self.assertEqual(miss["range"]["result"], "miss")

    def test_line_is_one_complete_lossless_compact_row_per_symbol(self):
        payload = {"market": "TW", "window": "post_close_1500", "tracking_symbols": FIXTURE["tracking_symbols"], "structured_review_cards": self.cards}
        line = render_line(payload, "TW", "post_close_1500", URL)
        for symbol in FIXTURE["tracking_symbols"]:
            self.assertEqual(line.count(symbol), 1)
        self.assertIn("009816 中信科技｜方向：符合｜區間：符合", line)
        self.assertIn("方向：5/8 符合（62.5%）｜區間：1/8 符合（12.5%）", line)
        self.assertIn("有效樣本：方向 8｜區間 8", line)
        self.assertIn("6873 泓德能源｜方向：不適用（未產生方向預測）｜區間：不適用（未產生區間預測）", line)
        self.assertIn("2330 台積電｜方向：符合｜區間：部分符合", line)
        self.assertIn(URL, line)
        self.assertNotIn("資料不足：方向評估所需證據不足", line)
        self.assertLessEqual(len(line), 520)
        self.assertTrue(batch_gate(self.cards, market="TW", window="post_close_1500")["line_send_allowed"])

    def test_dashboard_projection_preserves_original_evidence(self):
        payload = {"market": "TW", "window": "post_close_1500", "structured_review_cards": self.cards}
        projected = project_payload(payload, "TW", "post_close_1500")
        self.assertEqual(projected["cards"][0]["evidence"], self.cards[0])
        fields = {field["label"]: field["value"] for field in projected["cards"][0]["fields"]}
        self.assertEqual(fields["方向預測結果"], "符合預測")
        self.assertEqual(fields["區間預測結果"], "部分符合")

    def test_dashboard_keeps_not_applicable_reason_distinct_from_missing_data(self):
        payload = {"market": "TW", "window": "post_close_1500", "structured_review_cards": self.cards}
        projected = {card["symbol"]: card for card in project_payload(payload, "TW", "post_close_1500")["cards"]}
        fields = {field["label"]: field["value"] for field in projected["6873"]["fields"]}
        self.assertEqual(fields["方向預測結果"], "不適用（未提供正式方向預測）")
        self.assertEqual(fields["區間預測結果"], "不適用（未提供正式區間預測）")
        self.assertNotIn("資料不足", fields["方向預測結果"])


if __name__ == "__main__":
    unittest.main()
