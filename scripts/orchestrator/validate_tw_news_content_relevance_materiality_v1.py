#!/usr/bin/env python3
"""Validate TW news content extraction and relevance/materiality admission."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.news_content_relevance import enrich_news_items, extract_article_text, fetch_article_content  # noqa: E402
from app.reports.tw_pre_open_quality import news_contract  # noqa: E402

NOW = "2026-09-17T07:00:00+08:00"


class _Response:
    def __init__(self, text: str, status_code: int = 200, url: str = "https://news.example/article") -> None:
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.encoding = "utf-8"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int = 65536):
        raw = self.text.encode("utf-8")
        for index in range(0, len(raw), chunk_size):
            yield raw[index:index + chunk_size]

    def close(self) -> None:
        return None


class _Session:
    def __init__(self, mapping: dict[str, _Response | Exception]) -> None:
        self.mapping = mapping
        self.calls: list[str] = []

    def get(self, url: str, **_kwargs: Any) -> _Response:
        self.calls.append(url)
        value = self.mapping[url]
        if isinstance(value, Exception):
            raise value
        return value


def _html(body: str) -> str:
    return f"""
    <html><head><meta name="description" content="fixture"></head>
    <body><nav>navigation</nav><article><h1>新聞</h1><p>{body}</p></article></body></html>
    """


def _item(title: str, url: str = "https://news.example/article") -> dict[str, Any]:
    return {
        "title": title,
        "source": "中央社",
        "published": "2026-09-17T06:20:00+08:00",
        "link": url,
    }


def _contract(items: list[dict[str, Any]], symbol: str, name: str) -> dict[str, Any]:
    return news_contract({"items": items, "retrieval": {"sources_attempted": ["GOOGLE_NEWS_RSS"], "sources_succeeded": ["GOOGLE_NEWS_RSS"], "result_count_raw": len(items)}}, generated_at=NOW, target_symbol=symbol, target_name=name)


def run_validation() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    extracted = extract_article_text(_html("台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。公司說明產能利用率維持高檔，資本支出與供應鏈合作延續，對後續營運展望具有明確影響。"))
    checks["html_content_extracted_without_nav"] = "navigation" not in extracted.lower() and "月營收成長" in extracted

    tsmc_session = _Session({
        "https://news.example/tsmc": _Response(_html("台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。公司說明產能利用率維持高檔，資本支出與供應鏈合作延續，對後續營運展望具有明確影響。")),
    })
    tsmc_items, tsmc_stats = enrich_news_items([_item("台積電月營收成長", "https://news.example/tsmc")], stock_id="2330", stock_name="台積電", session=tsmc_session)
    tsmc_contract = _contract(tsmc_items, "2330", "台積電")
    checks["2330_content_relevance_materiality_admitted"] = (
        tsmc_stats["admission_ready"] == 1
        and tsmc_contract["evidence_funnel"]["stages"]["ADMITTED"] == 1
        and tsmc_contract["evidence"][0]["relevance"] in {"medium", "high"}
        and tsmc_contract["evidence"][0]["materiality"] in {"high", "critical"}
    )
    details["2330"] = {"stats": tsmc_stats, "funnel": tsmc_contract["evidence_funnel"]}

    igs_session = _Session({
        "https://news.example/igs": _Response(_html("鈊象 3293 遊戲業務動能延續，營收與海外市場需求增加，法人看好訂單能見度。公司遊戲產品海外授權與平台合作擴大，對未來獲利與市場展望具有明確影響。")),
    })
    igs_items, igs_stats = enrich_news_items([_item("鈊象遊戲業務動能延續", "https://news.example/igs")], stock_id="3293", stock_name="鈊象", session=igs_session)
    igs_contract = _contract(igs_items, "3293", "鈊象")
    checks["3293_content_relevance_materiality_admitted"] = igs_stats["admission_ready"] == 1 and igs_contract["evidence_funnel"]["stages"]["ADMITTED"] == 1
    details["3293"] = {"stats": igs_stats, "funnel": igs_contract["evidence_funnel"]}

    no_content_session = _Session({"https://news.example/empty": _Response("<html><body><p>short</p></body></html>")})
    no_content_items, no_content_stats = enrich_news_items([_item("台積電重大消息", "https://news.example/empty")], stock_id="2330", stock_name="台積電", session=no_content_session)
    no_content_contract = _contract(no_content_items, "2330", "台積電")
    checks["content_fetch_failure_remains_fail_closed"] = (
        no_content_stats["admission_ready"] == 0
        and "relevance" not in no_content_items[0]
        and no_content_contract["evidence_funnel"]["rejection_reasons"].get("RELEVANCE_NOT_EVALUATED") == 1
    )

    unrelated_session = _Session({"https://news.example/acer": _Response(_html("宏碁 2353 商用筆電新品上市，訂單需求增加。公司指出商用通路庫存回補，AI PC 產品銷售改善，對宏碁後續營收展望具有明確影響。此消息內容聚焦宏碁品牌與個人電腦市場，未涉及其他半導體供應鏈公司事件。"))})
    unrelated_items, unrelated_stats = enrich_news_items([_item("宏碁新品上市", "https://news.example/acer")], stock_id="2330", stock_name="台積電", session=unrelated_session)
    unrelated_contract = _contract(unrelated_items, "2330", "台積電")
    checks["unrelated_article_rejected_without_relevance_fields"] = (
        unrelated_stats["rejection_reasons"].get("CONTENT_SYMBOL_EVIDENCE_MISSING") == 1
        and unrelated_contract["evidence_funnel"]["rejection_reasons"].get("SYMBOL_ATTRIBUTION_FAILED") == 1
    )

    etf_session = _Session({"https://news.example/company": _Response(_html("台積電 2330 月營收成長，先進製程訂單增加。"))})
    etf_items, etf_stats = enrich_news_items([_item("台積電月營收成長", "https://news.example/company")], stock_id="00878", stock_name="國泰永續高股息", session=etf_session)
    etf_contract = _contract(etf_items, "00878", "國泰永續高股息")
    checks["etf_does_not_apply_company_news"] = (
        etf_stats["rejection_reasons"].get("ETF_COMPANY_NEWS_NOT_APPLICABLE") == 1
        and etf_contract["evidence_funnel"]["stages"]["ADMITTED"] == 0
    )

    low_value_session = _Session({"https://news.example/forum": _Response(_html("台積電 2330 投資人討論股價能買嗎，未提供營運或財務新增事實。文章主要整理討論區留言與投資人情緒，缺乏公司公告、財務數據、產能、訂單或客戶需求的新事實。"))})
    low_items, low_stats = enrich_news_items([_item("2330 台積電 - 股市爆料同學會", "https://news.example/forum")], stock_id="2330", stock_name="台積電", session=low_value_session)
    low_contract = _contract(low_items, "2330", "台積電")
    checks["low_value_forum_content_rejected"] = (
        low_stats["rejection_reasons"].get("LOW_VALUE_METADATA_OR_FORUM_CONTENT") == 1
        and low_contract["evidence_funnel"]["rejection_reasons"].get("LOW_RELEVANCE") == 1
    )

    duplicate_session = _Session({
        "https://news.example/dup": _Response(_html("台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。公司說明產能利用率維持高檔，資本支出與供應鏈合作延續，對後續營運展望具有明確影響。")),
    })
    dup_items, dup_stats = enrich_news_items([
        _item("台積電月營收成長", "https://news.example/dup"),
        _item("台積電展望改善", "https://news.example/dup"),
    ], stock_id="2330", stock_name="台積電", session=duplicate_session)
    checks["duplicate_url_fetched_once"] = len(duplicate_session.calls) == 1 and dup_stats["admission_ready"] == 2 and all(item.get("content") for item in dup_items)

    direct_failure = fetch_article_content("ftp://news.example/bad")
    checks["untrusted_url_rejected"] = direct_failure.fetch_status == "failed" and direct_failure.failure_reason == "UNTRUSTED_OR_INVALID_URL"

    redirect_session = _Session({"https://news.example/redirect": _Response(_html("台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。公司說明產能利用率維持高檔，資本支出與供應鏈合作延續，對後續營運展望具有明確影響。"), url="ftp://evil.example/article")})
    redirected = fetch_article_content("https://news.example/redirect", session=redirect_session)
    checks["untrusted_redirect_rejected"] = redirected.fetch_status == "failed" and redirected.failure_reason == "UNTRUSTED_REDIRECT_URL"

    large_session = _Session({"https://news.example/large": _Response("<html><body><article>" + ("台積電 " * 250000) + "</article></body></html>")})
    large = fetch_article_content("https://news.example/large", session=large_session)
    checks["oversized_response_rejected"] = large.fetch_status == "failed" and large.failure_reason == "RESPONSE_TOO_LARGE"

    return {
        "schema_version": "tw_news_content_relevance_materiality_validation_v1",
        "ok": all(checks.values()),
        "passed_count": sum(1 for value in checks.values() if value),
        "total_count": len(checks),
        "checks": checks,
        "details": details,
        "safety": {
            "production_rerun": False,
            "line_or_email_sent": False,
            "db_or_sheet_write": False,
            "scheduler_mutation": False,
            "credential_access": False,
            "trading_or_order": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = run_validation()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
