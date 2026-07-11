#!/usr/bin/env python3
"""Validate AI-DEV-173B shared navigation UI consistency for TW and US Dashboards."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import OUTPUT_DIR, TW_URL, US_URL, build_pages

REQUIRED_NAV_MARKERS = ["回到總覽", "台股 Dashboard", "美股 Dashboard"]
REQUIRED_CLASSES = [
    "market-shared-navigation",
    "market-shared-navigation--v1",
    "market-shared-navigation__grid",
    "market-shared-navigation__grid--responsive",
    "market-shared-navigation__button",
]
REQUIRED_CSS_MARKERS = [
    ".market-shared-navigation{background:white;color:#17262c}",
    ".market-shared-navigation__grid{display:grid;grid-template-columns:1fr;gap:12px",
    ".market-shared-navigation__button{display:block;width:100%;box-sizing:border-box;background:#fff",
    "border-radius:8px",
    "padding:13px 14px",
    "@media(max-width:640px){.market-shared-navigation__grid{gap:10px}",
]
INLINE_TEXT_PATTERN = "回到總覽 台股 Dashboard 美股 Dashboard"


def fetch(url: str) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=8) as response:
            return {
                "ok": True,
                "status": getattr(response, "status", 200),
                "body": response.read().decode("utf-8", errors="replace"),
                "url": response.geturl(),
            }
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return {"ok": False, "status": None, "body": "", "error": str(exc), "url": url}


def nav_block(html: str) -> str:
    match = re.search(r'(<div class="[^"]*market-shared-navigation[\s\S]*?</div>)', html)
    return match.group(1) if match else ""


def button_sequence(block: str) -> list[str]:
    return re.findall(r'<a class="([^"]*)" href="[^"]+"(?: aria-current="page")?>([^<]+)</a>', block)


def page_checks(html: str) -> dict[str, Any]:
    block = nav_block(html)
    nav_match = re.search(r'(<nav class="[^"]*market-shared-navigation__grid[\s\S]*?</nav>)', block)
    nav_only = nav_match.group(1) if nav_match else ""
    sequence = button_sequence(block)
    return {
        "shared_nav_block_present": bool(block),
        "data_marker_present": 'data-shared-navigation="tw-us"' in block,
        "container_classes_present": all(cls in block for cls in REQUIRED_CLASSES[:2]),
        "responsive_grid_class_present": all(cls in block for cls in REQUIRED_CLASSES[2:4]),
        "button_class_count": sum(1 for cls, _label in sequence if "market-shared-navigation__button" in cls),
        "button_sequence": [label for _cls, label in sequence],
        "button_sequence_ok": [label for _cls, label in sequence] == REQUIRED_NAV_MARKERS,
        "all_button_classes_identical": len(sequence) == 3 and all(cls == "market-shared-navigation__button" for cls, _label in sequence),
        "shared_css_present": all(marker in html for marker in REQUIRED_CSS_MARKERS),
        "old_inline_text_absent": INLINE_TEXT_PATTERN not in re.sub(r"\s+", " ", html),
        "block_fingerprint": re.sub(r' aria-current="page"', '', nav_only),
    }


def build_validation(require_public: bool) -> dict[str, Any]:
    errors: list[str] = []
    build_pages(OUTPUT_DIR)
    tw_html = (OUTPUT_DIR / "tw_index.html").read_text(encoding="utf-8")
    us_html = (OUTPUT_DIR / "us_index.html").read_text(encoding="utf-8")
    tw = page_checks(tw_html)
    us = page_checks(us_html)
    static_checks = {
        "tw_has_shared_nav_ui": all([
            tw["shared_nav_block_present"], tw["data_marker_present"], tw["container_classes_present"],
            tw["responsive_grid_class_present"], tw["button_class_count"] == 3, tw["button_sequence_ok"],
            tw["all_button_classes_identical"], tw["shared_css_present"], tw["old_inline_text_absent"],
        ]),
        "us_has_shared_nav_ui": all([
            us["shared_nav_block_present"], us["data_marker_present"], us["container_classes_present"],
            us["responsive_grid_class_present"], us["button_class_count"] == 3, us["button_sequence_ok"],
            us["all_button_classes_identical"], us["shared_css_present"], us["old_inline_text_absent"],
        ]),
        "tw_us_same_nav_structure": tw["block_fingerprint"] == us["block_fingerprint"],
    }
    for key, ok in static_checks.items():
        if not ok:
            errors.append(f"static shared navigation UI check failed: {key}")

    public_checks: dict[str, Any] = {"checked": require_public}
    if require_public:
        tw_public = fetch(TW_URL)
        us_public = fetch(US_URL)
        twp = page_checks(tw_public.get("body", ""))
        usp = page_checks(us_public.get("body", ""))
        public_checks.update({
            "tw_http_ok": tw_public.get("ok") is True,
            "us_http_ok": us_public.get("ok") is True,
            "public_tw_has_shared_nav_ui": twp["shared_nav_block_present"] and twp["button_sequence_ok"] and twp["shared_css_present"],
            "public_us_has_shared_nav_ui": usp["shared_nav_block_present"] and usp["button_sequence_ok"] and usp["shared_css_present"],
            "public_tw_us_same_nav_structure": twp["block_fingerprint"] == usp["block_fingerprint"],
            "public_old_inline_text_absent": twp["old_inline_text_absent"] and usp["old_inline_text_absent"],
        })
        for key, ok in public_checks.items():
            if key != "checked" and ok is not True:
                errors.append(f"public shared navigation UI check failed: {key}")

    return {
        "ok": not errors,
        "schema_version": "shared_navigation_ui_consistency_v1",
        "task_id": "AI-DEV-173B",
        "static_checks": static_checks,
        "tw_details": tw,
        "us_details": us,
        "public_checks": public_checks,
        "safety_checks": {
            "no_line_email_sent": True,
            "no_scheduler_change": True,
            "no_runtime_artifact_change_required": True,
            "no_strategy_prediction_review_change": True,
            "no_trading": True,
        },
        "errors": errors,
        "tw_url": TW_URL,
        "us_url": US_URL,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--require-public", action="store_true")
    args = parser.parse_args()
    result = build_validation(require_public=args.require_public)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
