"""AI-DEV-290: synthetic fallback and transport regression. No network or sends."""
import unittest
from unittest.mock import patch, Mock

from app.us_stock.news_rss_fallback import fetch_us_google_news_rss
from app.research.news_evidence_funnel import normalize_yfinance_news
from scripts.orchestrator.approved_us_stock_delivery import send_line_if_allowed, send_email_if_allowed

ASOF = "2026-10-29T20:00:00+08:00"
RSS = b"""<rss><channel><item>
<title>Tesla announces battery production update</title>
<link>https://news.google.com/rss/articles/test</link>
<pubDate>Thu, 29 Oct 2026 10:00:00 GMT</pubDate>
<source url="https://example.com">Synthetic Finance</source>
</item></channel></rss>"""


class NewsFallbackTests(unittest.TestCase):
    def test_bounded_rss_candidate_passes_unchanged_admission(self):
        response = Mock(content=RSS)
        response.raise_for_status.return_value = None
        with patch("app.us_stock.news_rss_fallback.requests.get", return_value=response) as get:
            rows, error = fetch_us_google_news_rss("TSLA")
        self.assertIsNone(error)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["discovery_channel"], "GOOGLE_NEWS_RSS")
        self.assertEqual(get.call_args.kwargs["timeout"], 8)
        admitted, evidence = normalize_yfinance_news(rows, symbol="TSLA", observed_at=ASOF)
        self.assertEqual(len(admitted), 1)
        self.assertEqual(admitted[0]["discovery_channel"], "GOOGLE_NEWS_RSS")
        self.assertEqual(evidence["stages"]["ADMITTED"], 1)

    def test_live_client_uses_fallback_when_yahoo_empty(self):
        import pandas as pd
        from app.us_stock.live_data import YFinanceUSClient
        from datetime import datetime
        from zoneinfo import ZoneInfo
        ticker = Mock()
        ticker.fast_info = {"last_price": 402.0, "previous_close": 400.0}
        ticker.get_info.return_value = {}
        ticker.history.return_value = pd.DataFrame({"Close": [399.0, 402.0]})
        ticker.news = []
        client = YFinanceUSClient()
        client._ticker_cache["TSLA"] = ticker
        client.news_as_of = datetime(2026, 10, 29, 20, tzinfo=ZoneInfo("Asia/Taipei"))
        rss = [{
            "title": "Tesla battery production update",
            "publisher": "Synthetic Finance",
            "pubDate": "2026-10-29T10:00:00Z",
            "link": "https://news.google.com/rss/articles/test",
            "contentType": "STORY",
            "discovery_channel": "GOOGLE_NEWS_RSS",
        }]
        with patch("app.us_stock.news_rss_fallback.fetch_us_google_news_rss", return_value=(rss, None)):
            result = client.fetch_symbol("TSLA")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.news), 1)
        self.assertEqual(result.news_diagnostics["source_attempts"]["YAHOO_FINANCE"]["candidate_count"], 0)
        self.assertEqual(result.news_diagnostics["source_attempts"]["GOOGLE_NEWS_RSS"]["candidate_count"], 1)

    def test_rss_source_survives_research_and_user_presentation(self):
        from app.us_stock.research_intelligence import USResearchIntelligenceBuilder
        from app.us_stock.institutional_research import build_bundle
        from app.us_stock.research_presentation import finalized_current_news_projection
        row = {
            "title": "Tesla announces battery production update",
            "publisher": "Synthetic Finance",
            "pubDate": "2026-10-29T10:00:00Z",
            "link": "https://news.google.com/rss/articles/test",
            "contentType": "STORY",
            "discovery_channel": "GOOGLE_NEWS_RSS",
        }
        admitted, diagnostics = normalize_yfinance_news([row], symbol="TSLA", observed_at=ASOF)
        material = USResearchIntelligenceBuilder.material_news(
            object.__new__(USResearchIntelligenceBuilder), "TSLA", admitted, diagnostics,
        )
        bundle = build_bundle("TSLA", {"sec": {"ok": False}, "material_news": material}, {}, ASOF)
        projection = finalized_current_news_projection(bundle)
        self.assertEqual(projection["selected_count"], 1)
        self.assertEqual(projection["primary_item"]["discovery_channel"], "GOOGLE_NEWS_RSS")
        self.assertEqual(projection["funnel"]["stages"]["RENDERED"], 1)

    def test_wrong_company_and_stale_news_still_rejected(self):
        response = Mock(content=RSS)
        with patch("app.us_stock.news_rss_fallback.requests.get", return_value=response):
            rows, error = fetch_us_google_news_rss("GOOGL")
        self.assertIsNone(error)
        accepted, evidence = normalize_yfinance_news(rows, symbol="GOOGL", observed_at=ASOF)
        self.assertEqual(accepted, [])
        self.assertEqual(evidence["stages"]["ADMITTED"], 0)
        accepted, evidence = normalize_yfinance_news(rows, symbol="TSLA", observed_at="2026-11-05T20:00:00+08:00")
        self.assertEqual(accepted, [])

    def test_provider_failure_is_not_silent_success(self):
        import requests
        with patch("app.us_stock.news_rss_fallback.requests.get", side_effect=requests.Timeout):
            rows, error = fetch_us_google_news_rss("TSLA")
        self.assertEqual(rows, [])
        self.assertEqual(error, "Timeout")
        rows, error = fetch_us_google_news_rss("UNKNOWN")
        self.assertEqual(rows, [])
        self.assertEqual(error, "UNSUPPORTED_SYMBOL")


class USNotificationTests(unittest.TestCase):
    def test_immutable_channel_receipts_prevent_duplicate_send(self):
        import tempfile
        from pathlib import Path
        from scripts.orchestrator.approved_us_stock_delivery import send_us_channel_with_receipt
        snapshot = {
            "market": "US", "window": "us_pre_market_2000",
            "effective_trading_date": "2026-10-29",
            "generated_at": ASOF,
            "revision": 1, "snapshot_id": "us-test-snapshot-1",
            "payload": {"synthetic": True},
        }
        with tempfile.TemporaryDirectory() as tmp, \
             patch("scripts.orchestrator.approved_us_stock_delivery.line_text", return_value="test report"), \
             patch("scripts.orchestrator.approved_us_stock_delivery.send_line_if_allowed",
                   return_value={"attempted": True, "succeeded": True, "recipient_transport": [
                       {"recipient": "test-user", "status": "accepted"}]}) as send:
            first = send_us_channel_with_receipt(
                {}, "us_pre_market_2000", "line", snapshot, Path(tmp))
            second = send_us_channel_with_receipt(
                {}, "us_pre_market_2000", "line", snapshot, Path(tmp))
            self.assertEqual(send.call_count, 1)
            self.assertTrue(first["succeeded"])
            self.assertTrue(second["succeeded"])
            self.assertFalse(second["attempted"])
            self.assertEqual(first["recipient_count"], 1)
            self.assertNotIn("test-user", Path(first["receipt_path"]).read_text())

    def test_failed_channel_has_terminal_receipt_no_automatic_resend(self):
        import tempfile
        from pathlib import Path
        from scripts.orchestrator.approved_us_stock_delivery import send_us_channel_with_receipt
        snapshot = {
            "market": "US", "window": "us_pre_market_2000",
            "effective_trading_date": "2026-10-29",
            "revision": 1, "snapshot_id": "us-failed-test",
            "payload": {"synthetic": True},
        }
        with tempfile.TemporaryDirectory() as tmp, \
             patch("scripts.orchestrator.approved_us_stock_delivery.line_text", return_value="failed report"), \
             patch("scripts.orchestrator.approved_us_stock_delivery.send_line_if_allowed",
                   return_value={"attempted": True, "succeeded": False,
                                 "reason": "line_transport_failure"}) as send:
            first = send_us_channel_with_receipt(
                {}, "us_pre_market_2000", "line", snapshot, Path(tmp))
            second = send_us_channel_with_receipt(
                {}, "us_pre_market_2000", "line", snapshot, Path(tmp))
            self.assertFalse(first["succeeded"])
            self.assertFalse(second["succeeded"])
            self.assertFalse(second["attempted"])
            self.assertEqual(send.call_count, 1)

    @patch("scripts.orchestrator.approved_us_stock_delivery.line_text", return_value="report")
    @patch("reports.line_report_sender.get_line_user_ids", return_value=["u1", "u2"])
    @patch("reports.line_report_sender.send_line_report", return_value=[("u1", 200), ("u2", 200)])
    def test_line_all_recipients_accepted(self, sender, recipients, text):
        result = send_line_if_allowed({}, "us_pre_market_2000", True)
        self.assertTrue(result["succeeded"])
        self.assertEqual(result["recipient_count"], 2)
        self.assertEqual(result["chunk_delivery"]["completed_chunk_count"], 1)

    @patch("scripts.orchestrator.approved_us_stock_delivery.line_text", return_value="report")
    @patch("reports.line_report_sender.get_line_user_ids", return_value=["u1", "u2"])
    @patch("reports.line_report_sender.send_line_report", return_value=[("u1", 200)])
    def test_line_partial_receipt_is_failure(self, sender, recipients, text):
        result = send_line_if_allowed({}, "us_pre_market_2000", True)
        self.assertFalse(result["succeeded"])
        self.assertEqual(result["recipient_count"], 0)

    @patch("scripts.orchestrator.approved_us_stock_delivery.line_text", return_value="text" * 2000)
    @patch("reports.line_report_sender.get_line_user_ids", return_value=["u1"])
    @patch("reports.line_report_sender.send_line_report", return_value=[("u1", 200)])
    def test_line_long_report_uses_lossless_chunks(self, sender, recipients, text):
        result = send_line_if_allowed({}, "us_pre_market_2000", True)
        self.assertTrue(result["succeeded"])
        self.assertGreater(result["chunk_delivery"]["chunk_count"], 1)

    @patch("scripts.orchestrator.approved_us_stock_delivery.load_mail_config", return_value={"to_addr": "a@example.com,b@example.com"})
    @patch("scripts.orchestrator.approved_us_stock_delivery.build_email_subject", return_value="subject")
    @patch("scripts.orchestrator.approved_us_stock_delivery.build_email_body", return_value="body")
    @patch("scripts.orchestrator.approved_us_stock_delivery.build_message")
    @patch("scripts.orchestrator.approved_us_stock_delivery.send_message", return_value={"b@example.com": (550, b"refused")})
    def test_email_partial_recipient_refusal(self, send, message, body, subject, config):
        result = send_email_if_allowed({}, "us_pre_market_2000", True)
        self.assertFalse(result["succeeded"])
        self.assertEqual(result["recipient_count"], 1)
        self.assertEqual(result["rejected_count"], 1)


if __name__ == "__main__":
    unittest.main()
