#!/usr/bin/env python3
"""Validate dashboard de-duplication, news layering, localization, and mobile CSS."""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import OUTPUT_DIR, build_pages


HTML_PATHS = {
    "tw": OUTPUT_DIR / "tw_index.html",
    "us": OUTPUT_DIR / "us_index.html",
}

FORBIDDEN_MAIN_LABELS = [
    "Daily Tactical",
    "Direction",
    "Setup",
    "Action",
    "Entry Zone",
    "Stop",
    "Target",
    "Prediction",
    "Research",
    "Financial Quality",
    "Official Events",
    "Material News",
    "Technical Detail",
    "Runtime Metadata",
    "Source Freshness",
    "Strategy ID",
    "Factor Version",
]

FORBIDDEN_RAW_TOKENS = [
    "live market data fetched",
    "metadata checked",
    "available_reference",
    "news metadata",
    "us_daily_tactical_factor_v1",
]


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def visible_text(html: str) -> str:
    parser = VisibleTextParser()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def stock_cards(html: str) -> list[str]:
    return re.findall(r"<article class=\"stock-card decision-card us-stock-card\".*?</article>", html, flags=re.S)


def between(text: str, start: str, end: str) -> str:
    start_at = text.find(start)
    if start_at < 0:
        return ""
    end_at = text.find(end, start_at + len(start))
    if end_at < 0:
        return text[start_at:]
    return text[start_at:end_at]


def list_section_text(card_text: str, heading: str) -> str:
    return between(card_text, heading, "</section>")


def duplicate_check(cards: list[str]) -> dict[str, Any]:
    fields = {
        "主要依據": [],
        "主要風險": [],
        "近期新聞與事件": [],
    }
    for card in cards:
        text = visible_text(card)
        for heading in fields:
            fields[heading].append(list_section_text(text, heading))
    result: dict[str, Any] = {}
    for heading, values in fields.items():
        unique = sorted(set(values))
        result[heading] = {
            "count": len(values),
            "unique": len(unique),
            "duplicated_100_percent": len(values) > 1 and len(unique) == 1,
            "sample": unique[:3],
        }
    return result


def card_has_meaningless_main_conflict(card: str) -> bool:
    text = visible_text(card)
    has_plan = all(marker in text for marker in ["進場區", "停損／失效價", "第一目標", "報酬風險比"])
    if not has_plan:
        return False
    main_text = text.split("技術與系統細節")[0]
    forbidden_generic = ["整體資料不足", "目前沒有足夠依據"]
    return any(token in main_text for token in forbidden_generic)


def build_validation() -> dict[str, Any]:
    manifest = build_pages(OUTPUT_DIR)
    errors: list[str] = []
    page_checks: dict[str, Any] = {}
    html_by_page = {name: path.read_text(encoding="utf-8") for name, path in HTML_PATHS.items()}
    for name, html in html_by_page.items():
        text = visible_text(html)
        forbidden_labels = [token for token in FORBIDDEN_MAIN_LABELS if re.search(rf"(^|\s){re.escape(token)}($|\s|：)", text)]
        raw_tokens = [token for token in FORBIDDEN_RAW_TOKENS if token in text]
        page_checks[name] = {
            "forbidden_english_labels": forbidden_labels,
            "raw_metadata_tokens": raw_tokens,
            "technical_details_collapsed": "技術與系統細節" in text and "<details class=\"decision-details\" open" not in html,
        }
        if forbidden_labels:
            errors.append(f"{name}: forbidden English labels visible: {forbidden_labels}")
        if raw_tokens:
            errors.append(f"{name}: raw metadata tokens visible: {raw_tokens}")
        if not page_checks[name]["technical_details_collapsed"]:
            errors.append(f"{name}: technical details not collapsed or missing Chinese title")

    us_cards = stock_cards(html_by_page["us"])
    news_layer_checks = []
    for index, card in enumerate(us_cards, start=1):
        text = visible_text(card)
        check = {
            "card_index": index,
            "has_news_section": "近期新聞與事件" in text,
            "has_official_layer": "重大官方事件" in text,
            "has_market_layer": "近期市場新聞" in text,
            "has_data_status": "新聞資料狀態" in text,
            "no_unsafe_fallback": all(token not in text for token in ["未取得可安全引用新聞", "Vocabulary：資料待接"]),
            "no_main_conflict": not card_has_meaningless_main_conflict(card),
        }
        news_layer_checks.append(check)
        for key, ok in check.items():
            if key != "card_index" and not ok:
                errors.append(f"us card {index}: {key} failed")

    duplicate = duplicate_check(us_cards)
    for heading, check in duplicate.items():
        if check["duplicated_100_percent"]:
            errors.append(f"US {heading}: 100% duplicated across stock cards")

    css = re.search(r"<style>(.*?)</style>", html_by_page["us"], flags=re.S)
    css_text = css.group(1) if css else ""
    mobile_css = {
        "safe_area": "env(safe-area-inset-left)" in css_text and "env(safe-area-inset-right)" in css_text,
        "overflow_guard": "overflow-x:hidden" in css_text,
        "wrapping": "overflow-wrap:anywhere" in css_text and "word-break:break-word" in css_text,
        "mobile_grid": "@media(max-width:640px)" in css_text and "grid-template-columns:1fr" in css_text,
        "card_padding": ".stock-card,.status-card" in css_text and "padding:16px" in css_text,
    }
    for key, ok in mobile_css.items():
        if not ok:
            errors.append(f"mobile css missing {key}")

    return {
        "ok": not errors,
        "schema_version": "dashboard_dedup_news_localization_mobile_validation_v1",
        "task_id": "AI-DEV-177A",
        "manifest_schema_version": manifest.get("schema_version"),
        "page_checks": page_checks,
        "us_stock_card_count": len(us_cards),
        "news_layer_checks": news_layer_checks,
        "duplicate_checks": duplicate,
        "mobile_css": mobile_css,
        "errors": errors,
        "safety": {
            "notifications_sent": False,
            "production_pipeline_executed": False,
            "strategy_modified": False,
            "scheduler_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = build_validation()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
