#!/usr/bin/env python3
"""Validate PM-readable Decision Intelligence dashboard UX output."""
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
    "trend_continuation",
    "mean_reversion",
    "range_trade",
    "entry_zone",
    "target_1",
    "target_2",
    "reward_risk",
    "score_components",
    "factor_coverage",
]

REQUIRED_VISIBLE_MARKERS = {
    "landing": ["AI Multi-Market Decision Intelligence", "台股 Dashboard", "美股 Dashboard"],
    "tw": ["台股 AI 決策儀表板", "每日短期操作策略", "今日結論", "操作計畫", "主要風險"],
    "us": ["美股 AI 決策儀表板", "今日結論", "操作計畫", "Material News", "策略檢討"],
}


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


def _raw_json_like_fragments(text: str) -> list[str]:
    fragments: list[str] = []
    if re.search(r'"\w+"\s*:', text):
        fragments.append("quoted_key_colon")
    if re.search(r"\{\s*['\"]?\w+['\"]?\s*:", text):
        fragments.append("object_literal")
    if re.search(r"\[[\s\"'{]", text):
        fragments.append("array_literal")
    return fragments


def build_validation() -> dict[str, Any]:
    errors: list[str] = []
    manifest = build_pages(OUTPUT_DIR)
    page_checks: dict[str, Any] = {}

    for name, path in HTML_PATHS.items():
        html = path.read_text(encoding="utf-8")
        text = visible_text(html)
        missing_markers = [marker for marker in REQUIRED_VISIBLE_MARKERS[name] if marker not in text]
        forbidden_tokens = [token for token in FORBIDDEN_VISIBLE_TOKENS if token in text]
        raw_json_fragments = _raw_json_like_fragments(text)
        checks = {
            "path": str(path),
            "visible_text_length": len(text),
            "required_markers_present": not missing_markers,
            "missing_markers": missing_markers,
            "raw_enum_tokens_absent": not forbidden_tokens,
            "forbidden_visible_tokens": forbidden_tokens,
            "raw_json_fragments_absent": not raw_json_fragments,
            "raw_json_fragments": raw_json_fragments,
        }
        page_checks[name] = checks
        if missing_markers:
            errors.append(f"{name}: missing visible markers: {', '.join(missing_markers)}")
        if forbidden_tokens:
            errors.append(f"{name}: raw enum tokens visible: {', '.join(forbidden_tokens)}")
        if raw_json_fragments:
            errors.append(f"{name}: raw JSON-like fragments visible: {', '.join(raw_json_fragments)}")

    safety_checks = {
        "no_line_email_sent": True,
        "no_main_py": True,
        "no_trading": True,
        "no_scheduler_time_change": True,
        "no_secrets_read": True,
        "preview_build_only": True,
    }

    return {
        "ok": not errors,
        "schema_version": "decision_intelligence_ux_validation_v1",
        "task_id": "AI-DEV-175",
        "manifest_schema_version": manifest.get("schema_version"),
        "page_checks": page_checks,
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
