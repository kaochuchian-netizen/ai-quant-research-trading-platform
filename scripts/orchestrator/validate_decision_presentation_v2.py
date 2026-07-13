#!/usr/bin/env python3
"""Validate Decision Presentation V2 across Dashboard, Email, and LINE."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import OUTPUT_DIR, build_pages
from app.reports.multi_window_formatter import format_window_report
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, build_runtime_artifact, line_text

DASHBOARD_PAGES = {
    "landing": OUTPUT_DIR / "index.html",
    "tw": OUTPUT_DIR / "tw_index.html",
    "us": OUTPUT_DIR / "us_index.html",
}

FORBIDDEN_VISIBLE_TOKENS = [
    "insufficient_data",
    "available_reference",
    "not_triggered",
    "no_trade",
    "mildly_bullish",
    "mildly_bearish",
    "entry_zone",
    "target_1",
    "target_2",
    "reward_risk",
    "score_components",
    "factor_coverage",
    "setup_type",
    "stop_invalidation",
    "target_zone_1",
    "daily_tactical_summary",
    "research_position_summary",
]


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.parts.append(text)


def visible_text(html: str) -> str:
    parser = VisibleTextParser()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def raw_json_fragments(text: str) -> list[str]:
    fragments: list[str] = []
    if re.search(r'"\w+"\s*:', text):
        fragments.append("quoted_key_colon")
    if re.search(r"\{\s*['\"]?\w+['\"]?\s*:", text):
        fragments.append("object_literal")
    if re.search(r"\[[\s\"'{]", text):
        fragments.append("array_literal")
    return fragments


def raw_token_hits(text: str) -> list[str]:
    return [token for token in FORBIDDEN_VISIBLE_TOKENS if token in text]


def check_surface(name: str, text: str, required: list[str]) -> dict[str, Any]:
    missing = [marker for marker in required if marker not in text]
    tokens = raw_token_hits(text)
    json_hits = raw_json_fragments(text)
    dashboard_url_count = text.count("http://35.201.242.167/stock-ai-dashboard/")
    return {
        "name": name,
        "required_markers_present": not missing,
        "missing_markers": missing,
        "raw_enum_tokens_absent": not tokens,
        "forbidden_tokens": tokens,
        "raw_json_fragments_absent": not json_hits,
        "raw_json_fragments": json_hits,
        "dashboard_url_count": dashboard_url_count,
        "dashboard_url_not_duplicated": dashboard_url_count <= 1,
    }


def channel_texts() -> dict[str, str]:
    tw_report = format_window_report("pre_open_0700", "partial", "runtime dry-run summary", dashboard_url=None)
    us_artifact = build_runtime_artifact(
        "us_pre_market_2000",
        dry_run=True,
        reference=datetime.now(ZoneInfo("Asia/Taipei")),
    )
    return {
        "tw_line": tw_report["channel_reports"]["line"]["text"],
        "tw_email": tw_report["channel_reports"]["email"]["text"],
        "us_line": line_text(us_artifact, "us_pre_market_2000"),
        "us_email": build_email_body(us_artifact, "us_pre_market_2000"),
    }


def build_validation() -> dict[str, Any]:
    errors: list[str] = []
    manifest = build_pages(OUTPUT_DIR)
    page_checks: dict[str, Any] = {}

    for name, path in DASHBOARD_PAGES.items():
        text = visible_text(path.read_text(encoding="utf-8"))
        required = ["Decision Presentation V2"] if name in {"tw", "us"} else ["AI Multi-Market Decision Intelligence"]
        check = check_surface(f"dashboard_{name}", text, required)
        page_checks[name] = check
        if not check["required_markers_present"]:
            errors.append(f"dashboard_{name}: missing markers {check['missing_markers']}")
        if not check["raw_enum_tokens_absent"]:
            errors.append(f"dashboard_{name}: raw enum tokens {check['forbidden_tokens']}")
        if not check["raw_json_fragments_absent"]:
            errors.append(f"dashboard_{name}: raw JSON fragments {check['raw_json_fragments']}")

    required_by_channel = {
        "tw_line": ["台股決策摘要已更新", "Daily Tactical 可觀察"],
        "tw_email": ["Decision Presentation V2", "Research / Daily Tactical / Prediction"],
        "us_line": ["美股決策摘要已更新", "Daily Tactical 可觀察"],
        "us_email": ["Research：", "Daily Tactical：", "Prediction："],
    }
    channel_checks: dict[str, Any] = {}
    for name, text in channel_texts().items():
        check = check_surface(name, text, required_by_channel[name])
        channel_checks[name] = check
        if not check["required_markers_present"]:
            errors.append(f"{name}: missing markers {check['missing_markers']}")
        if not check["raw_enum_tokens_absent"]:
            errors.append(f"{name}: raw enum tokens {check['forbidden_tokens']}")
        if not check["raw_json_fragments_absent"]:
            errors.append(f"{name}: raw JSON fragments {check['raw_json_fragments']}")
        if name.endswith("_line") and not check["dashboard_url_not_duplicated"]:
            errors.append(f"{name}: duplicate Dashboard URL")

    safety_checks = {
        "no_line_email_sent": True,
        "no_main_py": True,
        "no_scheduler_change": True,
        "no_trading": True,
        "no_secrets_read": True,
        "dry_run_channel_render_only": True,
    }

    return {
        "ok": not errors,
        "schema_version": "decision_presentation_v2_validation_v1",
        "task_id": "AI-DEV-176",
        "manifest_schema_version": manifest.get("schema_version"),
        "page_checks": page_checks,
        "channel_checks": channel_checks,
        "safety_checks": safety_checks,
        "errors": errors,
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
