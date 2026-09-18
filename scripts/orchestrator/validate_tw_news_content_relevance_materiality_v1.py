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

from app.research.tw_news_content_relevance import (  # noqa: E402
    CnyesBrowserContentCache,
    CnyesSearchConfig,
    build_cnyes_article_fetch_queue,
    build_cnyes_target_window,
    collect_cnyes_browser_news,
    collect_cnyes_time_window_results,
    cnyes_search_result_from_dom,
    enrich_news_items,
    extract_article_text,
    fetch_article_content,
    parse_cnyes_dom_timestamp,
)
from app.reports.tw_pre_open_quality import news_contract  # noqa: E402

NOW = "2026-09-17T07:00:00+08:00"


class _Response:
    def __init__(
        self,
        text: str,
        status_code: int = 200,
        url: str = "https://news.example/article",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.text = text
        self.status_code = status_code
        self.url = url
        self.headers = {"content-type": "text/html; charset=utf-8"}
        if headers:
            self.headers.update(headers)
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
        self.resolved_ips: list[str | None] = []

    def get(self, url: str, **_kwargs: Any) -> _Response:
        self.calls.append(url)
        self.resolved_ips.append(_kwargs.get("resolved_ip"))
        value = self.mapping[url]
        if isinstance(value, Exception):
            raise value
        return value


class _BrowserAdapter:
    def __init__(self, batches: list[list[dict[str, Any]]], article_bodies: dict[str, str] | None = None, *, fail: str | None = None) -> None:
        self.batches = batches
        self.article_bodies = article_bodies or {}
        self.fail = fail
        self.index = 0
        self.opened_search_urls: list[str] = []
        self.opened_articles: list[str] = []
        self.waited_results = False

    def _raise_if_needed(self) -> None:
        if self.fail == "timeout":
            raise TimeoutError("selenium explicit wait timeout")
        if self.fail == "protection":
            raise RuntimeError("Cloudflare security challenge blocked")
        if self.fail == "crash":
            raise RuntimeError("chrome not reachable")

    def open_search(self, url: str) -> None:
        self.opened_search_urls.append(url)
        self._raise_if_needed()

    def wait_results_ready(self) -> None:
        self.waited_results = True
        self._raise_if_needed()

    def visible_result_cards(self) -> list[dict[str, Any]]:
        self._raise_if_needed()
        return self.batches[0] if self.batches else []

    def scroll_for_more(self, _current_count: int) -> list[dict[str, Any]]:
        self._raise_if_needed()
        self.index += 1
        if self.index >= len(self.batches):
            return []
        return self.batches[self.index]

    def open_article(self, url: str) -> None:
        self.opened_articles.append(url)
        self._raise_if_needed()

    def article_body(self) -> str:
        if not self.opened_articles:
            return ""
        return self.article_bodies.get(self.opened_articles[-1], "")


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


def _public_resolver(_hostname: str, _port: int | None = None) -> list[str]:
    return ["93.184.216.34"]


def _private_resolver(_hostname: str, _port: int | None = None) -> list[str]:
    return ["10.0.0.5"]


def _contract(items: list[dict[str, Any]], symbol: str, name: str) -> dict[str, Any]:
    return news_contract({"items": items, "retrieval": {"sources_attempted": ["GOOGLE_NEWS_RSS"], "sources_succeeded": ["GOOGLE_NEWS_RSS"], "result_count_raw": len(items)}}, generated_at=NOW, target_symbol=symbol, target_name=name)


def _cnyes(title: str, day: str, article_id: int, *, status: str = "TITLE_ONLY", content: str = "") -> dict[str, Any]:
    return {
        "title": title,
        "published_at": f"{day}T09:00:00+08:00",
        "url": f"https://news.cnyes.com/news/id/{article_id}",
        "source": "鉅亨網",
        "content_status": status,
        "content": content,
    }


def run_validation() -> dict[str, Any]:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    requirements_text = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    checks["cnyes_selenium_runtime_dependency_declared"] = any(
        line.strip().startswith("selenium==")
        for line in requirements_text.splitlines()
    )

    extracted = extract_article_text(_html("台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。公司說明產能利用率維持高檔，資本支出與供應鏈合作延續，對後續營運展望具有明確影響，並補充海外主要客戶需求穩定。"))
    checks["html_content_extracted_without_nav"] = "navigation" not in extracted.lower() and "月營收成長" in extracted

    tsmc_session = _Session({
        "https://news.example/tsmc": _Response(_html("台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。公司說明產能利用率維持高檔，資本支出與供應鏈合作延續，對後續營運展望具有明確影響，並補充海外主要客戶需求穩定。")),
    })
    tsmc_items, tsmc_stats = enrich_news_items([_item("台積電月營收成長", "https://news.example/tsmc")], stock_id="2330", stock_name="台積電", session=tsmc_session, resolver=_public_resolver)
    tsmc_contract = _contract(tsmc_items, "2330", "台積電")
    checks["2330_content_relevance_materiality_admitted"] = (
        tsmc_stats["admission_ready"] == 1
        and tsmc_contract["evidence_funnel"]["stages"]["ADMITTED"] == 1
        and tsmc_contract["evidence"][0]["relevance"] in {"medium", "high"}
        and tsmc_contract["evidence"][0]["materiality"] in {"high", "critical"}
    )
    checks["transport_receives_verified_public_ip"] = tsmc_session.resolved_ips == ["93.184.216.34"]
    details["2330"] = {"stats": tsmc_stats, "funnel": tsmc_contract["evidence_funnel"]}

    igs_session = _Session({
        "https://news.example/igs": _Response(_html("鈊象 3293 遊戲業務動能延續，營收與海外市場需求增加，法人看好訂單能見度。公司遊戲產品海外授權與平台合作擴大，對未來獲利與市場展望具有明確影響。")),
    })
    igs_items, igs_stats = enrich_news_items([_item("鈊象遊戲業務動能延續", "https://news.example/igs")], stock_id="3293", stock_name="鈊象", session=igs_session, resolver=_public_resolver)
    igs_contract = _contract(igs_items, "3293", "鈊象")
    checks["3293_content_relevance_materiality_admitted"] = igs_stats["admission_ready"] == 1 and igs_contract["evidence_funnel"]["stages"]["ADMITTED"] == 1
    details["3293"] = {"stats": igs_stats, "funnel": igs_contract["evidence_funnel"]}

    no_content_session = _Session({"https://news.example/empty": _Response("<html><body><p>short</p></body></html>")})
    no_content_items, no_content_stats = enrich_news_items([_item("台積電重大消息", "https://news.example/empty")], stock_id="2330", stock_name="台積電", session=no_content_session, resolver=_public_resolver)
    no_content_contract = _contract(no_content_items, "2330", "台積電")
    checks["content_fetch_failure_remains_fail_closed"] = (
        no_content_stats["admission_ready"] == 0
        and "relevance" not in no_content_items[0]
        and no_content_contract["evidence_funnel"]["rejection_reasons"].get("RELEVANCE_NOT_EVALUATED") == 1
    )

    unrelated_session = _Session({"https://news.example/acer": _Response(_html("宏碁 2353 商用筆電新品上市，訂單需求增加。公司指出商用通路庫存回補，AI PC 產品銷售改善，對宏碁後續營收展望具有明確影響。此消息內容聚焦宏碁品牌與個人電腦市場，未涉及其他半導體供應鏈公司事件。"))})
    unrelated_items, unrelated_stats = enrich_news_items([_item("宏碁新品上市", "https://news.example/acer")], stock_id="2330", stock_name="台積電", session=unrelated_session, resolver=_public_resolver)
    unrelated_contract = _contract(unrelated_items, "2330", "台積電")
    checks["unrelated_article_rejected_without_relevance_fields"] = (
        unrelated_stats["rejection_reasons"].get("CONTENT_SYMBOL_EVIDENCE_MISSING") == 1
        and unrelated_contract["evidence_funnel"]["rejection_reasons"].get("SYMBOL_ATTRIBUTION_FAILED") == 1
    )

    etf_session = _Session({"https://news.example/company": _Response(_html("台積電 2330 月營收成長，先進製程訂單增加。"))})
    etf_items, etf_stats = enrich_news_items([_item("台積電月營收成長", "https://news.example/company")], stock_id="00878", stock_name="國泰永續高股息", session=etf_session, resolver=_public_resolver)
    etf_contract = _contract(etf_items, "00878", "國泰永續高股息")
    checks["etf_does_not_apply_company_news"] = (
        etf_stats["rejection_reasons"].get("ETF_COMPANY_NEWS_NOT_APPLICABLE") == 1
        and etf_contract["evidence_funnel"]["stages"]["ADMITTED"] == 0
    )

    low_value_session = _Session({"https://news.example/forum": _Response(_html("台積電 2330 投資人討論股價能買嗎，未提供營運或財務新增事實。文章主要整理討論區留言與投資人情緒，缺乏公司公告、財務數據、產能、訂單或客戶需求的新事實。"))})
    low_items, low_stats = enrich_news_items([_item("2330 台積電 - 股市爆料同學會", "https://news.example/forum")], stock_id="2330", stock_name="台積電", session=low_value_session, resolver=_public_resolver)
    low_contract = _contract(low_items, "2330", "台積電")
    checks["low_value_forum_content_rejected"] = (
        low_stats["rejection_reasons"].get("LOW_VALUE_METADATA_OR_FORUM_CONTENT") == 1
        and low_contract["evidence_funnel"]["rejection_reasons"].get("LOW_RELEVANCE") == 1
    )

    duplicate_session = _Session({
        "https://news.example/dup": _Response(_html("台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。公司說明產能利用率維持高檔，資本支出與供應鏈合作延續，對後續營運展望具有明確影響，並補充海外主要客戶需求穩定。")),
    })
    dup_items, dup_stats = enrich_news_items([
        _item("台積電月營收成長", "https://news.example/dup"),
        _item("台積電展望改善", "https://news.example/dup"),
    ], stock_id="2330", stock_name="台積電", session=duplicate_session, resolver=_public_resolver)
    checks["duplicate_url_fetched_once"] = len(duplicate_session.calls) == 1 and dup_stats["admission_ready"] == 2 and all(item.get("content") for item in dup_items)

    direct_failure = fetch_article_content("ftp://news.example/bad")
    checks["untrusted_url_rejected"] = direct_failure.fetch_status == "failed" and direct_failure.failure_reason == "UNTRUSTED_OR_INVALID_URL"

    initial_internal_session = _Session({})
    initial_internal = fetch_article_content("http://127.0.0.1/private", session=initial_internal_session)
    checks["internal_initial_url_rejected_before_request"] = (
        initial_internal.fetch_status == "failed"
        and initial_internal.failure_reason == "PRIVATE_OR_INTERNAL_URL"
        and initial_internal_session.calls == []
    )

    redirect_session = _Session({
        "https://news.example/redirect": _Response(
            "",
            status_code=302,
            url="https://news.example/redirect",
            headers={"location": "http://169.254.169.254/latest/meta-data"},
        )
    })
    redirected = fetch_article_content("https://news.example/redirect", session=redirect_session, resolver=_public_resolver)
    checks["internal_redirect_rejected_before_followup_request"] = (
        redirected.fetch_status == "failed"
        and redirected.failure_reason == "PRIVATE_OR_INTERNAL_URL"
        and redirect_session.calls == ["https://news.example/redirect"]
    )

    rebinding_session = _Session({
        "https://news.example/rebind": _Response(_html("台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。")),
    })
    rebound = fetch_article_content(
        "https://news.example/rebind",
        session=rebinding_session,
        resolver=_public_resolver,
        connection_resolver=_private_resolver,
    )
    checks["dns_rebinding_to_internal_fails_before_request"] = (
        rebound.fetch_status == "failed"
        and rebound.failure_reason == "PRIVATE_OR_INTERNAL_URL"
        and rebinding_session.calls == []
    )

    large_session = _Session({"https://news.example/large": _Response("<html><body><article>" + ("台積電 " * 250000) + "</article></body></html>")})
    large = fetch_article_content("https://news.example/large", session=large_session, resolver=_public_resolver)
    checks["oversized_response_rejected"] = large.fetch_status == "failed" and large.failure_reason == "RESPONSE_TOO_LARGE"

    friday_window = build_cnyes_target_window("2026-09-18", holiday_dates=set())
    checks["cnyes_friday_target_window_uses_current_and_previous_trading_days"] = (
        friday_window["target_trading_dates"] == ["2026-09-18", "2026-09-17"]
        and friday_window["target_window_start"].startswith("2026-09-17T00:00:00")
    )
    monday_window = build_cnyes_target_window("2026-09-21", holiday_dates=set())
    checks["cnyes_monday_target_window_uses_monday_and_friday"] = monday_window["target_trading_dates"] == ["2026-09-21", "2026-09-18"]
    holiday_window = build_cnyes_target_window("2026-09-21", holiday_dates={"2026-09-21"})
    checks["cnyes_holiday_rolls_to_prior_valid_tw_trading_day"] = holiday_window["target_trading_dates"] == ["2026-09-18", "2026-09-17"]
    non_trading_window = build_cnyes_target_window("2026-09-20", holiday_dates=set())
    checks["cnyes_non_trading_day_execution_uses_most_recent_trading_day"] = non_trading_window["target_trading_dates"] == ["2026-09-18", "2026-09-17"]

    only_today = collect_cnyes_time_window_results(
        [[_cnyes("台積電今日新聞一", "2026-09-18", 1001), _cnyes("台積電今日新聞二", "2026-09-18", 1002)]],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    checks["cnyes_initial_all_today_continues_until_bounded_exhaustion"] = (
        only_today["within_window_results"] == 2
        and only_today["scroll_stop_reason"] == "INPUT_EXHAUSTED_BEFORE_BOUNDARY"
    )

    today_previous_no_boundary = collect_cnyes_time_window_results(
        [[_cnyes("台積電今日新聞", "2026-09-18", 1010), _cnyes("台積電昨日新聞", "2026-09-17", 1011)]],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    checks["cnyes_today_previous_without_boundary_continues"] = (
        today_previous_no_boundary["within_window_results"] == 2
        and today_previous_no_boundary["scroll_stop_reason"] == "INPUT_EXHAUSTED_BEFORE_BOUNDARY"
    )

    boundary = collect_cnyes_time_window_results(
        [
            [_cnyes("台積電今日新聞", "2026-09-18", 1020), _cnyes("台積電昨日新聞", "2026-09-17", 1021)],
            [_cnyes("台積電昨日新聞二", "2026-09-17", 1022), _cnyes("台積電前日舊聞", "2026-09-16", 1023)],
            [_cnyes("不應載入的更舊新聞", "2026-09-15", 1024)],
        ],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    checks["cnyes_next_batch_older_than_previous_trading_day_stops"] = (
        boundary["scroll_stop_reason"] == "TRADING_WINDOW_BOUNDARY_REACHED"
        and boundary["within_window_results"] == 3
        and all("2026-09-16" not in item["published_at"] for item in boundary["articles"])
    )
    checks["cnyes_batch_freshness_evidence_complete"] = all(
        key in boundary
        for key in (
            "target_trading_dates", "target_window_start", "target_window_end",
            "search_scroll_rounds", "search_results_seen", "within_window_results",
            "older_than_window_seen", "scroll_stop_reason", "article_fetch_required",
            "article_fetch_attempted", "article_fetch_success", "article_fetch_failed",
            "oldest_result_seen", "newest_result_seen",
        )
    )

    pinned_old = collect_cnyes_time_window_results(
        [
            [_cnyes("置頂舊聞", "2026-09-16", 1030), _cnyes("台積電今日新聞", "2026-09-18", 1031)],
            [_cnyes("台積電昨日新聞", "2026-09-17", 1032), _cnyes("台積電前日舊聞", "2026-09-16", 1033)],
        ],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    checks["cnyes_pinned_old_article_does_not_prematurely_stop"] = pinned_old["search_scroll_rounds"] == 2 and pinned_old["within_window_results"] == 2

    duplicate_scroll = collect_cnyes_time_window_results(
        [
            [_cnyes("台積電今日新聞", "2026-09-18", 1040)],
            [_cnyes("台積電今日新聞 duplicate", "2026-09-18", 1040), _cnyes("台積電昨日新聞", "2026-09-17", 1041)],
        ],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    checks["cnyes_duplicate_articles_across_scroll_batches_deduped"] = duplicate_scroll["search_results_seen"] == 2 and duplicate_scroll["within_window_results"] == 2

    no_new = collect_cnyes_time_window_results(
        [[_cnyes("台積電今日新聞", "2026-09-18", 1050)], [_cnyes("台積電今日新聞 duplicate", "2026-09-18", 1050)]],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    checks["cnyes_no_new_results_bounded_stop"] = no_new["scroll_stop_reason"] == "NO_NEW_RESULTS"

    max_rounds = collect_cnyes_time_window_results(
        [[_cnyes(f"台積電今日新聞{i}", "2026-09-18", 1060 + i)] for i in range(4)],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
        config=CnyesSearchConfig(max_scroll_rounds=2),
    )
    checks["cnyes_max_scroll_rounds_protection"] = max_rounds["scroll_stop_reason"] == "MAX_SCROLL_ROUNDS_REACHED"

    max_results = collect_cnyes_time_window_results(
        [[_cnyes(f"台積電今日新聞{i}", "2026-09-18", 1070 + i) for i in range(5)]],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
        config=CnyesSearchConfig(max_search_results=3),
    )
    checks["cnyes_max_search_results_protection"] = max_results["scroll_stop_reason"] == "MAX_SEARCH_RESULTS_REACHED"

    max_duration = collect_cnyes_time_window_results(
        [[_cnyes("台積電今日新聞", "2026-09-18", 1080)]],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
        config=CnyesSearchConfig(max_search_duration_seconds=0.1),
        elapsed_seconds=1.0,
    )
    checks["cnyes_max_search_duration_protection"] = max_duration["scroll_stop_reason"] == "MAX_SEARCH_DURATION_REACHED"

    queue_case = collect_cnyes_time_window_results(
        [[
            _cnyes("今日已有全文", "2026-09-18", 1090, status="FULL_CONTENT", content="台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。"),
            _cnyes("今日待抓全文", "2026-09-18", 1091, status="TITLE_ONLY"),
            _cnyes("昨日部分內容", "2026-09-17", 1092, status="PARTIAL", content="台積電 2330"),
            _cnyes("前日舊聞不得抓全文", "2026-09-16", 1093, status="TITLE_ONLY"),
        ]],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    queue_urls = [item["url"] for item in queue_case["article_fetch_queue"]]
    checks["cnyes_only_target_window_articles_enter_body_fetch_queue"] = all("1093" not in url for url in queue_urls)
    checks["cnyes_newest_article_fetched_first"] = queue_urls and queue_urls[0].endswith("/1091")
    checks["cnyes_old_article_never_triggers_body_request"] = all(not url.endswith("/1093") for url in queue_urls)
    checks["cnyes_title_only_within_window_triggers_body_fetch"] = any(url.endswith("/1091") for url in queue_urls)
    checks["cnyes_title_only_outside_window_does_not_trigger_body_fetch"] = not any(url.endswith("/1093") for url in queue_urls)
    checks["cnyes_full_content_within_window_does_not_trigger_body_fetch"] = not any(url.endswith("/1090") for url in queue_urls)

    direct_queue = build_cnyes_article_fetch_queue([
        _cnyes("今日已有全文", "2026-09-18", 1100, status="FULL_CONTENT", content="全文"),
        _cnyes("今日空白", "2026-09-18", 1101, status="EMPTY"),
    ])
    checks["cnyes_empty_within_window_triggers_body_fetch"] = len(direct_queue) == 1 and direct_queue[0]["url"].endswith("/1101")

    cnyes_0917_dom = cnyes_search_result_from_dom(
        href="https://news.cnyes.com/news/id/6609020",
        text="2026/09/17 雜誌 AI股新價值 台積電A14基地後年量產 先進製程大進補",
        datetime_attr="2026-09-17T15:11:34+08:00",
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    cnyes_0915_dom = cnyes_search_result_from_dom(
        href="https://news.cnyes.com/news/id/6606965",
        text="2026/09/15 台股盤後 盤後速報 - 台積電(2330)次交易(16)日除息7元，參考價2378.0元",
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    dom_boundary = collect_cnyes_time_window_results(
        [[
            cnyes_search_result_from_dom(
                href="https://news.cnyes.com/news/id/6609204",
                text="08:10 0918台股盤前｜台積電狂飆",
                datetime_attr="2026-09-18T08:10:06+08:00",
                symbol="2330",
                stock_name="台積電",
                reference="2026-09-18",
            ),
            cnyes_0917_dom,
            cnyes_0915_dom,
        ]],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
        config=CnyesSearchConfig(max_search_results=3),
    )
    checks["cnyes_2330_dom_20260917_parsed"] = cnyes_0917_dom["published_at"] == "2026-09-17T15:11:34+08:00"
    checks["cnyes_20260917_within_target_window"] = any(item["article_id"] == "6609020" for item in dom_boundary["articles"])
    checks["cnyes_20260915_out_of_target_window"] = all(item["article_id"] != "6606965" for item in dom_boundary["articles"])
    checks["cnyes_boundary_stop_precedence_over_max_results"] = dom_boundary["scroll_stop_reason"] == "TRADING_WINDOW_BOUNDARY_REACHED"
    mixed_layout = collect_cnyes_time_window_results(
        [[
            {"title": "台積電今日新聞", "published_at": "2026/09/18", "url": "https://news.cnyes.com/news/id/1301", "content_status": "TITLE_ONLY"},
            {"title": "台積電昨日新聞", "published_at": "09/17 15:11", "url": "https://news.cnyes.com/news/id/1302", "content_status": "TITLE_ONLY"},
            {"title": "台積電舊新聞", "published_at": "2026/09/15", "url": "https://news.cnyes.com/news/id/1303", "content_status": "TITLE_ONLY"},
        ]],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    checks["cnyes_timestamp_variants_parse"] = [item["article_id"] for item in mixed_layout["articles"]] == ["1301", "1302"]
    duplicate_newer = collect_cnyes_time_window_results(
        [[
            {"title": "台積電昨日新聞", "published_at": "2026/09/17", "url": "https://news.cnyes.com/news/id/1302", "content_status": "TITLE_ONLY"},
            {"title": "台積電舊新聞", "published_at": "2026/09/15", "url": "https://news.cnyes.com/news/id/1303", "content_status": "TITLE_ONLY"},
        ], [
            {"title": "台積電昨日新聞重複", "published_at": "2026/09/17", "url": "https://news.cnyes.com/news/id/1302?utm=dup", "content_status": "TITLE_ONLY"},
        ]],
        symbol="2330",
        stock_name="台積電",
        reference="2026-09-18",
    )
    checks["cnyes_dedup_does_not_drop_newer_article"] = [item["article_id"] for item in duplicate_newer["articles"]].count("1302") == 1
    checks["cnyes_mmdd_and_time_only_normalization"] = (
        parse_cnyes_dom_timestamp("09/17 15:11", reference="2026-09-18") == "2026-09-17T15:11:00+08:00"
        and parse_cnyes_dom_timestamp("08:10", reference="2026-09-18") == "2026-09-18T08:10:00+08:00"
    )

    checks["cnyes_selenium_dom_incremental_scroll_contract_declared"] = (
        boundary["search_method"] == "SELENIUM_BROWSER"
        and boundary["lazy_load_method"] == "DOM_INCREMENTAL_SCROLL"
        and boundary["article_method"] == "SELENIUM_BROWSER"
        and boundary["internal_json_endpoint"] == "NOT_PRODUCTION_DEPENDENCY"
    )
    browser = _BrowserAdapter(
        [
            [_cnyes("台積電今日待抓全文", "2026-09-18", 1200, status="TITLE_ONLY")],
            [_cnyes("台積電昨日已有全文", "2026-09-17", 1201, status="FULL_CONTENT", content="台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。公司說明產能利用率維持高檔，資本支出與供應鏈合作延續，對後續營運展望具有明確影響，並補充海外主要客戶需求穩定。"), _cnyes("台積電前日舊聞", "2026-09-16", 1202, status="TITLE_ONLY")],
        ],
        article_bodies={
            "https://news.cnyes.com/news/id/1200": "台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。公司說明產能利用率維持高檔，資本支出與供應鏈合作延續，對後續營運展望具有明確影響，並補充海外主要客戶需求穩定。"
        },
    )
    browser_result = collect_cnyes_browser_news(browser, symbol="2330", stock_name="台積電", reference="2026-09-18")
    checks["cnyes_browser_concurrency_one_declared"] = browser_result["browser_concurrency"] == 1
    checks["cnyes_browser_initial_dom_parsing"] = browser.waited_results and browser.opened_search_urls == ["https://www.cnyes.com/search/news?keyword=2330"]
    checks["cnyes_browser_incremental_scroll_growth"] = browser_result["search_scroll_rounds"] == 2 and browser_result["within_window_results"] == 2
    checks["cnyes_browser_boundary_stop"] = browser_result["scroll_stop_reason"] == "TRADING_WINDOW_BOUNDARY_REACHED"
    checks["cnyes_title_only_opens_article_page"] = browser.opened_articles == ["https://news.cnyes.com/news/id/1200"]
    checks["cnyes_full_content_does_not_open_article_page"] = "https://news.cnyes.com/news/id/1201" not in browser.opened_articles
    checks["cnyes_out_of_window_does_not_open_article_page"] = "https://news.cnyes.com/news/id/1202" not in browser.opened_articles
    checks["cnyes_article_body_extraction_to_full_content"] = browser_result["article_navigation_success"] == 1 and any(item.get("content_status") == "FULL_CONTENT" for item in browser_result["articles"])
    checks["cnyes_full_content_sets_success_fetch_status"] = any(
        item.get("content_status") == "FULL_CONTENT" and item.get("fetch_status") == "success"
        for item in browser_result["articles"]
    )
    pre_fetched_items, pre_fetched_stats = enrich_news_items(
        [{
            "title": "AI股新價值 台積電A14基地後年量產 先進製程大進補",
            "url": "https://news.cnyes.com/news/id/6609020",
            "published_at": "2026-09-17T15:11:34+08:00",
            "source": "鉅亨網",
            "content": "台積電 2330 先進製程 A14 基地後年量產，先進製程需求升溫，產能與資本支出增加，客戶訂單能見度提高，對營收與營運展望具有明確影響。公司說明先進製程布局與供應鏈合作延續，市場需求穩定，法人看好後續動能。",
            "content_status": "FULL_CONTENT",
            "fetch_status": "success",
        }],
        stock_id="2330",
        stock_name="台積電",
        fetch_content=False,
    )
    checks["cnyes_prefetched_full_content_evaluates_without_http_refetch"] = (
        pre_fetched_stats["admission_ready"] == 1
        and pre_fetched_items[0].get("relevance") in {"medium", "high"}
        and pre_fetched_items[0].get("materiality") in {"high", "critical"}
    )
    checks["cnyes_observability_navigation_counts"] = (
        browser_result["deduplicated_articles"] == 2
        and browser_result["article_navigation_required"] == 1
        and browser_result["article_navigation_attempted"] == 1
        and browser_result["browser_timeout_count"] == 0
        and browser_result["protection_blocked_count"] == 0
        and browser_result["browser_crash_count"] == 0
        and browser_result["usable_for_analysis_count"] == 2
    )
    checks["cnyes_retention_no_permanent_full_text_mirror"] = browser_result["retention_policy"]["persist_full_article_corpus"] is False

    malformed_article = _BrowserAdapter(
        [[_cnyes("台積電今日空白文章", "2026-09-18", 1210, status="TITLE_ONLY")]],
        article_bodies={"https://news.cnyes.com/news/id/1210": "短"},
    )
    malformed_result = collect_cnyes_browser_news(malformed_article, symbol="2330", stock_name="台積電", reference="2026-09-18")
    checks["cnyes_malformed_article_dom_fail_closed"] = malformed_result["article_navigation_failed"] == 1 and malformed_result["usable_for_analysis_count"] == 0

    timeout_result = collect_cnyes_browser_news(_BrowserAdapter([], fail="timeout"), symbol="2330", stock_name="台積電", reference="2026-09-18")
    checks["cnyes_browser_timeout_fail_closed"] = timeout_result["browser_timeout_count"] == 1 and timeout_result["scroll_stop_reason"] == "BROWSER_TIMEOUT"
    protection_result = collect_cnyes_browser_news(_BrowserAdapter([], fail="protection"), symbol="2330", stock_name="台積電", reference="2026-09-18")
    checks["cnyes_protection_challenge_fail_closed"] = protection_result["protection_blocked_count"] == 1 and protection_result["scroll_stop_reason"] == "PROTECTION_BLOCKED"
    crash_result = collect_cnyes_browser_news(_BrowserAdapter([], fail="crash"), symbol="2330", stock_name="台積電", reference="2026-09-18")
    checks["cnyes_browser_crash_fail_closed"] = crash_result["browser_crash_count"] == 1 and crash_result["scroll_stop_reason"] == "BROWSER_CRASH"

    shared_cache = CnyesBrowserContentCache()
    shared_url = "https://news.cnyes.com/news/id/1220"
    first_browser = _BrowserAdapter([[_cnyes("台積電共同新聞", "2026-09-18", 1220, status="TITLE_ONLY")]], article_bodies={shared_url: "台積電 2330 月營收成長，先進製程需求升溫，客戶訂單能見度提高。公司說明產能利用率維持高檔，資本支出與供應鏈合作延續，對後續營運展望具有明確影響，並補充海外主要客戶需求穩定。"})
    second_browser = _BrowserAdapter([[_cnyes("鈊象共同新聞", "2026-09-18", 1220, status="TITLE_ONLY")]], article_bodies={shared_url: "鈊象 3293 遊戲業務動能延續，營收與海外市場需求增加，法人看好訂單能見度。公司遊戲產品海外授權與平台合作擴大，對未來獲利與市場展望具有明確影響。"})
    first_shared = collect_cnyes_browser_news(first_browser, symbol="2330", stock_name="台積電", reference="2026-09-18", content_cache=shared_cache)
    second_shared = collect_cnyes_browser_news(second_browser, symbol="3293", stock_name="鈊象", reference="2026-09-18", content_cache=shared_cache)
    checks["cnyes_multi_symbol_article_page_opened_once"] = (
        first_shared["article_navigation_attempted"] == 1
        and second_shared["article_navigation_attempted"] == 0
        and first_browser.opened_articles == [shared_url]
        and second_browser.opened_articles == []
    )
    details["cnyes_2330_acceptance_case"] = {
        "initial_results": ["2026-09-18", "2026-09-17"],
        "incremental_load": ["2026-09-17", "2026-09-16"],
        "scroll_stop_reason": boundary["scroll_stop_reason"],
        "target_trading_dates": boundary["target_trading_dates"],
        "retained_articles": [{"title": item["title"], "published_at": item["published_at"], "url": item["url"], "content_status": item["content_status"]} for item in boundary["articles"]],
        "article_fetch_queue": [{"title": item["title"], "published_at": item["published_at"], "url": item["url"], "content_status": item["content_status"]} for item in boundary["article_fetch_queue"]],
        "lazy_load_method": boundary["lazy_load_method"],
        "search_method": boundary["search_method"],
        "article_method": boundary["article_method"],
        "architecture_rationale": "CNYES production collection uses Selenium/Chrome DOM incremental scroll and browser article navigation; internal JSON endpoints are not production dependencies.",
        "browser_result": {
            "article_navigation_attempted": browser_result["article_navigation_attempted"],
            "article_navigation_success": browser_result["article_navigation_success"],
            "article_navigation_failed": browser_result["article_navigation_failed"],
            "usable_for_analysis_count": browser_result["usable_for_analysis_count"],
            "retention_policy": browser_result["retention_policy"],
        },
    }

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
