"""AI-DEV-302 closure: TW 07:00 email must preserve every frozen forecast.

Synthetic-only, no Production files, network, transport, or batch execution.
"""
from copy import deepcopy
import re
import unittest

from app.reports.tw_pre_open_structured import render_email
from app.reports.tw_preopen_product_intelligence import render_line as product_line
from tests.test_ai_dev_283 import inputs


class TwPreopenEmailForecastParity(unittest.TestCase):
    def test_ten_frozen_cards_complete_and_in_original_order(self):
        pre, _ = inputs(10, current=True)
        payload = pre["payload"]
        cards = payload["structured_pre_open_cards"]
        frozen = deepcopy(payload)
        for idx, card in enumerate(cards):
            symbol = str(card["symbol"])
            card["tw_preopen_product_intelligence_v1"] = {
                "symbol": symbol,
                "direction_label": ("偏多", "偏空", "盤整")[idx % 3],
                "direction_arrow": ("↑", "↓", "↔")[idx % 3],
                "predicted_low": 100.0 + idx,
                "predicted_high": 105.5 + idx,
                "target_price": 102.25 + idx,
                "decision": {"action": ("等待", "觀察", "暫不交易")[idx % 3]},
                "news_funnel": {"retrieved_count": 0, "selected_count": 0},
            }
        rendered = render_email(payload, "https://preview.invalid/tw")
        line = product_line(cards, "https://preview.invalid/tw")
        rows = [row for row in rendered.splitlines() if row.startswith("- ") and "｜方向：" in row]
        self.assertEqual(len(rows), 10)
        self.assertEqual([row.split(" ", 2)[1] for row in rows],
                         [card["symbol"] for card in cards])
        for idx, card in enumerate(cards):
            product = card["tw_preopen_product_intelligence_v1"]
            symbol = card["symbol"]
            low = str(int(product["predicted_low"]))
            high = str(product["predicted_high"]).rstrip("0").rstrip(".")
            target = str(product["target_price"]).rstrip("0").rstrip(".")
            self.assertIn(f"{symbol} {product['direction_label']}", line)
            self.assertIn(f"區間{low}～{high}", line)
            self.assertIn(f"方向：{product['direction_label']}", rows[idx])
            self.assertIn(f"預測區間：{low}～{high}", rows[idx])
            self.assertIn(f"預測目標：{target}", rows[idx])
            self.assertIn(f"決策：{product['decision']['action']}", rows[idx])
        self.assertEqual(
            [c["symbol"] for c in payload["structured_pre_open_cards"]],
            [c["symbol"] for c in frozen["structured_pre_open_cards"]]
        )

    def test_legacy_cards_reuse_dashboard_projection_without_mutation(self):
        pre, _ = inputs(10, current=True)
        payload = pre["payload"]
        frozen = deepcopy(payload)
        rendered = render_email(payload, "https://preview.invalid/tw")
        rows = [row for row in rendered.splitlines() if row.startswith("- ") and "｜方向：" in row]
        self.assertEqual(len(rows), 10)
        for row in rows:
            for label in ("方向：", "預測區間：", "預測目標：", "決策："):
                self.assertIn(label, row)
        self.assertEqual(payload, frozen)

    def test_no_unrelated_status_codes_in_new_email_rows(self):
        pre, _ = inputs(10, current=True)
        for card in pre["payload"]["structured_pre_open_cards"]:
            card["tw_preopen_product_intelligence_v1"] = {
                "direction_label": "偏空", "predicted_low": 10, "predicted_high": 11,
                "target_price": 10.5, "decision": {"action": "暫不交易"},
            }
        rendered = render_email(pre["payload"], "https://preview.invalid/tw")
        rows = [row for row in rendered.splitlines() if "｜方向：" in row]
        self.assertEqual(len(rows), 10)
        self.assertFalse(re.search(r"\\b(?:TECHNICAL_ONLY|UNAVAILABLE|UNKNOWN)\\b", "\n".join(rows)))


if __name__ == "__main__":
    unittest.main()
