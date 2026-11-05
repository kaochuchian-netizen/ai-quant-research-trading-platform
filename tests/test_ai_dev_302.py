"""AI-DEV-302: public Traditional Chinese presentation of frozen decision enums.

No pipeline, transport, market fetch, Production state or mutable artifacts.
"""
from __future__ import annotations

from copy import deepcopy
import json
import re
import unittest

from app.prediction.technical_first import KEY, status_text
from app.prediction.technical_first_adapters import apply_us
from app.reports.mobile_decision_presentation import render_primary, render_line
from scripts.orchestrator.approved_us_stock_delivery import build_email_body
from tests.test_ai_dev_294 import ASOF, ENTRY, base, news_adjustment, final_decision

PUBLIC_ENUM_LEAK = re.compile(
    r"\b(?:TECHNICAL_ONLY|TECHNICAL_PLUS_NEWS|DATA_BLOCKED|"
    r"NO_RELEVANT_NEWS|UNAVAILABLE|UNQUANTIFIED|UNKNOWN)\b"
)


class PublicZhTwStatusTest(unittest.TestCase):
    def test_all_known_modes_news_and_event_risks_are_localized(self):
        modes = {
            "TECHNICAL_ONLY": "僅依技術分析",
            "TECHNICAL_PLUS_NEWS": "技術分析與新聞佐證",
            "DATA_BLOCKED": "技術資料不足",
        }
        news = {
            "AVAILABLE": "有可用新聞證據",
            "NO_RELEVANT_NEWS": "未取得符合條件的相關新聞",
            "UNAVAILABLE": "新聞資料無法取得",
        }
        event = {
            "high": "高風險",
            "UNQUANTIFIED": "尚未量化",
            "UNKNOWN": "尚無法判定",
        }
        for mode, mode_label in modes.items():
            for news_status, news_label in news.items():
                for risk, risk_label in event.items():
                    with self.subTest(mode=mode, news=news_status, risk=risk):
                        final = dict(mode=mode, news_status=news_status, event_risk=risk,
                                     technical_research_usable=True, confidence=70.0)
                        card = {KEY: {"final_decision": final}}
                        frozen = deepcopy(card)
                        label = status_text(card)
                        self.assertIn(mode_label, label)
                        self.assertIn(news_label, label)
                        self.assertIn(risk_label, label)
                        self.assertIn("70.0（技術信心，非校準勝率）", label)
                        self.assertNotRegex(label, PUBLIC_ENUM_LEAK)
                        self.assertEqual(card, frozen)

    def test_missing_unknown_legacy_and_invalid_confidence_fail_closed(self):
        self.assertEqual(status_text({}), "技術／新聞分層：舊產物未保存分層證據")
        card = {KEY: {"final_decision": {
            "mode": "FUTURE_MODE", "news_status": "FUTURE_STATUS",
            "event_risk": "FUTURE_RISK", "technical_research_usable": False,
            "confidence": float("nan"),
        }}}
        label = status_text(card)
        self.assertIn("分析依據：尚無法判定", label)
        self.assertIn("技術：資料不足", label)
        self.assertIn("新聞：尚無法判定", label)
        self.assertIn("事件風險：尚無法判定", label)
        self.assertIn("信心：尚未取得", label)
        self.assertNotIn("FUTURE_", label)
        self.assertNotIn("nan", label)

    def test_real_frozen_decision_shared_by_dashboard_line_email(self):
        b = base()
        decision = final_decision(
            b, news_adjustment(entry=ENTRY, as_of=ASOF, items=[],
                               retrieval={"status": "FAILED"})
        )
        card = apply_us({"symbol": "EXAM", "name": "Example Company"}, decision)
        before = json.dumps(card, ensure_ascii=False, sort_keys=True, default=str)
        payload = {"market": "US", "window": "us_pre_market_2000",
                   "effective_trading_date": "2026-11-02",
                   "dashboard_ready_contract": {"cards": [card]}}
        label = status_text(card)
        self.assertIn("僅依技術分析", label)
        self.assertIn("新聞：新聞資料無法取得", label)
        self.assertIn("事件風險：尚無法判定", label)
        outputs = {
            "dashboard": render_primary(payload, "US", "us_pre_market_2000"),
            "line": render_line(payload, "US", "us_pre_market_2000",
                                "https://example.invalid"),
            "email": build_email_body(payload, "us_pre_market_2000"),
        }
        for name, result in outputs.items():
            with self.subTest(channel=name):
                self.assertIn(label, result)
                self.assertNotRegex(result, PUBLIC_ENUM_LEAK)
        self.assertEqual(json.dumps(card, ensure_ascii=False, sort_keys=True, default=str), before)
        self.assertEqual(card[KEY], decision)
        self.assertEqual(decision["final_decision"]["mode"], "TECHNICAL_ONLY")
        self.assertEqual(decision["final_decision"]["news_status"], "UNAVAILABLE")

    def test_existing_public_summary_uses_same_localized_text(self):
        decision = final_decision(
            base(), news_adjustment(entry=ENTRY, as_of=ASOF, items=[],
                                    retrieval={"status": "FAILED"})
        )
        card = apply_us({"symbol": "EXAM", "name": "Example Company"}, decision)
        self.assertEqual(card["decision_basis_summary"], status_text(card))
        self.assertNotRegex(card["decision_basis_summary"], PUBLIC_ENUM_LEAK)


if __name__ == "__main__":
    unittest.main()
