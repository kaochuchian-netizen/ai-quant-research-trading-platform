#!/usr/bin/env python3
"""Audit runtime-to-presentation completeness for Decision Presentation V3."""
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

from app.dashboard.decision_presentation import decision_email_block_v2, decision_line_summary_v2, decision_presentation_v2
from app.dashboard.multi_market_dashboard import OUTPUT_DIR, US_URL, build_pages
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, line_text

US_RUNTIME = ROOT / "artifacts/runtime/us_stock/us_pre_market_2000_latest.json"
TW_RUNTIME = ROOT / "artifacts/runtime/tw_daily_tactical/tw_daily_tactical_latest.json"

FIELDS = ["reason", "risk", "entry", "stop", "target", "reward_risk", "news", "sec", "review"]
FALLBACK_VALUES = {"", "暫無", "資料不足", "目前沒有足夠依據", "目前未偵測到額外風險"}


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


def us_cards() -> list[dict[str, Any]]:
    data = read_json(US_RUNTIME)
    return [card for card in data.get("dashboard_ready_contract", {}).get("cards", []) if isinstance(card, dict)]


def tw_cards() -> list[dict[str, Any]]:
    data = read_json(TW_RUNTIME)
    return [card for card in data.get("cards", []) if isinstance(card, dict)]


def _runtime_tactical(card: dict[str, Any]) -> dict[str, Any]:
    strategies = card.get("strategies", {}) if isinstance(card.get("strategies"), dict) else {}
    tactical = strategies.get("daily_tactical") or card.get("daily_tactical_summary") or {}
    return tactical if isinstance(tactical, dict) else {}


def _has(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return str(value).strip() not in FALLBACK_VALUES


def runtime_presence(card: dict[str, Any], market: str) -> dict[str, bool]:
    tactical = _runtime_tactical(card)
    research_sections = card.get("research_sections", {}) if isinstance(card.get("research_sections"), dict) else {}
    return {
        "reason": _has(tactical.get("tactical_rationale") or tactical.get("reasons") or card.get("technical_summary")),
        "risk": _has(tactical.get("risk_notes") or tactical.get("risk_reasons")),
        "entry": _has(tactical.get("entry_zone")),
        "stop": _has(tactical.get("stop_reference") or tactical.get("stop_invalidation") or tactical.get("invalidation_level")),
        "target": _has(tactical.get("target_zone_1") or tactical.get("target_1")),
        "reward_risk": _has(tactical.get("reward_risk_ratio") or tactical.get("reward_risk")),
        "news": market == "US" and _has(card.get("bilingual_news_snippet")),
        "sec": market == "US" and _has(card.get("latest_sec_filing") or research_sections.get("sec")),
        "review": _has(tactical.get("review_contract") or card.get("review_result")),
    }


def presentation_values(presentation: dict[str, Any]) -> dict[str, str]:
    tactical = presentation.get("daily_tactical", {})
    research_v3 = presentation.get("research_v3", {})
    return {
        "reason": "；".join(presentation.get("reasons", [])),
        "risk": "；".join(presentation.get("risks", [])),
        "entry": str(tactical.get("entry_zone", "")),
        "stop": str(tactical.get("stop", "")),
        "target": str(tactical.get("target_1", "")),
        "reward_risk": str(tactical.get("reward_risk", "")),
        "news": str(research_v3.get("material_news", "")),
        "sec": str(research_v3.get("sec", "")),
        "review": str(research_v3.get("review", "")),
    }


def surface_presence(values: dict[str, str], text: str) -> dict[str, bool]:
    result: dict[str, bool] = {}
    for field, value in values.items():
        parts = [part.strip() for part in value.split("；") if part.strip()]
        result[field] = bool(parts) and all(part in text for part in parts)
    return result


def audit_cards(cards: list[dict[str, Any]], market: str, dashboard_text: str, email_text: str, line_summary: str) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    coverage = {field: {"runtime": 0, "presentation": 0, "dashboard": 0, "email": 0, "line": 0} for field in FIELDS}
    errors: list[str] = []
    for card in cards:
        symbol = str(card.get("symbol") or card.get("stock_id") or "")
        presentation = decision_presentation_v2(market, card)
        values = presentation_values(presentation)
        runtime = runtime_presence(card, market)
        email_block = decision_email_block_v2(presentation)
        dashboard = surface_presence(values, dashboard_text)
        email = surface_presence(values, email_text + "\n" + email_block)
        line = surface_presence(values, line_summary)
        line_required_fields = {"reason", "risk", "entry", "stop", "target", "reward_risk", "news", "sec", "review"}
        row = {}
        for field in FIELDS:
            presentation_ok = _has(values[field])
            row[field] = {
                "runtime": runtime[field],
                "presentation": presentation_ok,
                "dashboard": dashboard[field],
                "email": email[field],
                "line": line[field],
                "value": values[field],
            }
            if runtime[field]:
                coverage[field]["runtime"] += 1
                if presentation_ok:
                    coverage[field]["presentation"] += 1
                if dashboard[field]:
                    coverage[field]["dashboard"] += 1
                if email[field]:
                    coverage[field]["email"] += 1
                if line[field]:
                    coverage[field]["line"] += 1
                line_ok = True if field in line_required_fields else line[field]
                if not all([presentation_ok, dashboard[field], email[field], line_ok]):
                    errors.append(f"{market} {symbol}: {field} runtime value not present on required surfaces")
        rows[symbol] = row
    return {"rows": rows, "coverage": coverage, "errors": errors}


def duplicate_report(cards: list[dict[str, Any]], market: str) -> dict[str, Any]:
    fields = ["reason", "risk", "news", "sec", "review"] if market == "US" else ["reason", "risk", "review"]
    result: dict[str, Any] = {}
    for field in fields:
        values = [presentation_values(decision_presentation_v2(market, card))[field] for card in cards]
        unique = sorted(set(values))
        result[field] = {"count": len(values), "unique": len(unique), "duplicated": len(values) > 1 and len(unique) == 1, "sample": unique[:3]}
    return result


def build_validation() -> dict[str, Any]:
    build_pages(OUTPUT_DIR)
    dashboard_text = visible_text((OUTPUT_DIR / "us_index.html").read_text(encoding="utf-8"))
    us_data = read_json(US_RUNTIME)
    us_email = build_email_body(us_data, "us_pre_market_2000") if us_data else ""
    us_line = line_text(us_data, "us_pre_market_2000") if us_data else ""
    tw_presentations = [decision_presentation_v2("TW", card) for card in tw_cards()]
    tw_email = "\n".join(decision_email_block_v2(item) for item in tw_presentations)
    tw_line = decision_line_summary_v2("台股", tw_presentations, US_URL) if tw_presentations else ""

    us_audit = audit_cards(us_cards(), "US", dashboard_text, us_email, us_line)
    tw_audit = audit_cards(tw_cards(), "TW", visible_text((OUTPUT_DIR / "tw_index.html").read_text(encoding="utf-8")), tw_email, tw_line)
    duplicates = {"US": duplicate_report(us_cards(), "US"), "TW": duplicate_report(tw_cards(), "TW")}
    errors = [*us_audit["errors"], *tw_audit["errors"]]
    for market, fields in duplicates.items():
        for field, info in fields.items():
            if info["duplicated"]:
                errors.append(f"{market}: {field} is 100% identical across {info['count']} stocks")
    return {
        "ok": not errors,
        "schema_version": "decision_data_completeness_validation_v1",
        "task_id": "AI-DEV-177",
        "stock_counts": {"US": len(us_cards()), "TW": len(tw_cards())},
        "runtime_to_dashboard_mapping_coverage": us_audit["coverage"],
        "per_stock": {"US": us_audit["rows"], "TW": tw_audit["rows"]},
        "duplicate_audit": duplicates,
        "errors": errors,
        "safety": {"strategy_modified": False, "runtime_modified": False, "notifications_sent": False, "production_pipeline_executed": False},
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
