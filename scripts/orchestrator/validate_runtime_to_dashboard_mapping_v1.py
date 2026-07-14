#!/usr/bin/env python3
"""Validate that runtime fields used by Presentation V3 reach the dashboard."""
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

from app.dashboard.decision_presentation import decision_presentation_v2
from app.dashboard.multi_market_dashboard import OUTPUT_DIR, build_pages

US_RUNTIME = ROOT / "artifacts/runtime/us_stock/us_pre_market_2000_latest.json"
REQUIRED_FIELDS = ["entry_zone", "stop", "target", "reward_risk", "reason", "risk", "news", "sec", "review"]


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
    return re.sub(r"\s+", " ", " ".join(parser.parts))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def cards() -> list[dict[str, Any]]:
    data = read_json(US_RUNTIME)
    return [card for card in data.get("dashboard_ready_contract", {}).get("cards", []) if isinstance(card, dict)]


def tactical(card: dict[str, Any]) -> dict[str, Any]:
    strategies = card.get("strategies", {}) if isinstance(card.get("strategies"), dict) else {}
    value = strategies.get("daily_tactical") or card.get("daily_tactical_summary") or {}
    return value if isinstance(value, dict) else {}


def runtime_has(card: dict[str, Any], field: str) -> bool:
    t = tactical(card)
    mapping = {
        "entry_zone": t.get("entry_zone"),
        "stop": t.get("stop_reference") or t.get("stop_invalidation") or t.get("invalidation_level"),
        "target": t.get("target_zone_1") or t.get("target_1"),
        "reward_risk": t.get("reward_risk_ratio") or t.get("reward_risk"),
        "reason": t.get("tactical_rationale") or card.get("technical_summary"),
        "risk": t.get("risk_notes") or t.get("risk_reasons"),
        "news": card.get("bilingual_news_snippet"),
        "sec": card.get("latest_sec_filing") or (card.get("research_sections", {}) if isinstance(card.get("research_sections"), dict) else {}).get("sec"),
        "review": t.get("review_contract") or card.get("review_result"),
    }
    value = mapping[field]
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return bool(value)
    return bool(str(value).strip())


def presentation_value(card: dict[str, Any], field: str) -> str:
    p = decision_presentation_v2("US", card)
    t = p.get("daily_tactical", {})
    rv3 = p.get("research_v3", {})
    mapping = {
        "entry_zone": t.get("entry_zone"),
        "stop": t.get("stop"),
        "target": t.get("target_1"),
        "reward_risk": t.get("reward_risk"),
        "reason": "；".join(p.get("reasons", [])),
        "risk": "；".join(p.get("risks", [])),
        "news": rv3.get("material_news"),
        "sec": rv3.get("sec"),
        "review": rv3.get("review"),
    }
    return str(mapping[field] or "")


def build_validation() -> dict[str, Any]:
    build_pages(OUTPUT_DIR)
    html_text = visible_text((OUTPUT_DIR / "us_index.html").read_text(encoding="utf-8"))
    rows: dict[str, Any] = {}
    mapped = 0
    required = 0
    errors: list[str] = []
    for card in cards():
        symbol = str(card.get("symbol") or "")
        rows[symbol] = {}
        for field in REQUIRED_FIELDS:
            has_runtime = runtime_has(card, field)
            value = presentation_value(card, field)
            parts = [part.strip() for part in value.split("；") if part.strip()]
            in_dashboard = bool(parts) and all(part in html_text for part in parts)
            rows[symbol][field] = {"runtime": has_runtime, "presentation_value": value, "dashboard": in_dashboard}
            if has_runtime:
                required += 1
                if in_dashboard:
                    mapped += 1
                else:
                    errors.append(f"{symbol}: runtime field {field} missing from dashboard")
    coverage = 1.0 if required == 0 else mapped / required
    return {
        "ok": not errors,
        "schema_version": "runtime_to_dashboard_mapping_validation_v1",
        "task_id": "AI-DEV-177",
        "mapped_fields": mapped,
        "runtime_fields_requiring_mapping": required,
        "coverage": coverage,
        "per_stock": rows,
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
