import json
from pathlib import Path
import unittest

from app.reports.mobile_decision_presentation import project_payload, render_line
from app.reports.post_close_quality_gate import batch_gate, evaluate_card


FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "ai_dev_272_us_20261015_golden.json").read_text())


class DecisionQualityGateTests(unittest.TestCase):
    def test_real_immutable_us_golden_maps_boolean_direction_evaluation(self):
        aapl, nvda = FIXTURE["cards"]
        self.assertEqual(evaluate_card(aapl, market="US", window=FIXTURE["window"])["direction"]["result"], "hit")
        self.assertEqual(evaluate_card(nvda, market="US", window=FIXTURE["window"])["direction"]["result"], "miss")

    def test_us_line_has_no_false_missing_direction(self):
        payload = {"market":"US", "window":FIXTURE["window"], "structured_review_cards":FIXTURE["cards"]}
        text = render_line(payload, "US", FIXTURE["window"], "https://example.test/report")
        self.assertIn("方向預測結果：符合預測（預測：偏多／實際：偏多）", text)
        self.assertIn("方向預測結果：未符合預測（預測：偏多／實際：偏空）", text)
        self.assertIn("區間預測結果：符合預測（預測：334.98–348.92／實際：341.72–347.07）", text)
        self.assertNotIn("尚未取得正式資料", text)
        self.assertIn("AAPL", text)
        self.assertIn("NVDA", text)
        self.assertLess(len(text), 2000)

    def test_partial_evidence_is_explicit_not_success(self):
        card = {"symbol":"2330", "actual_low":100, "actual_high":102, "actual_close":101}
        value = evaluate_card(card, market="TW", window="post_close_1500")
        self.assertEqual(value["status"], "PARTIAL_EVIDENCE")
        self.assertEqual(value["direction"]["reason_code"], "DIRECTION_EVALUATION_NOT_ADMITTED")
        self.assertIsNone(value["range"]["result"])

    def test_cross_market_gate_isolated(self):
        self.assertEqual(batch_gate(FIXTURE["cards"], market="US", window=FIXTURE["window"])["status"], "QUALIFIED")
        tw = {"symbol":"2330", "actual_low":100, "actual_high":102, "actual_close":101,
              "direction_result":"hit", "prediction_range_result":"hit"}
        self.assertEqual(evaluate_card(tw, market="TW", window="post_close_1500")["status"], "EVALUATED")
        with self.assertRaises(ValueError):
            evaluate_card(FIXTURE["cards"][0], market="TW", window="us_post_close_review_0630")

    def test_no_silent_success_when_actual_is_missing(self):
        card = {"symbol":"AAPL", "source_trade_plan":{"forecast":{"direction":"BULLISH"}}, "review":{"prediction_evaluation_v2":{"direction":{"status":"evaluated","hit":True}}}, "prediction_range_result":"hit"}
        result = evaluate_card(card, market="US", window="us_post_close_review_0630")
        self.assertEqual(result["status"], "INSUFFICIENT_EVIDENCE")
        self.assertIsNone(result["range"]["result"])
