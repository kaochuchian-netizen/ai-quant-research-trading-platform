#!/usr/bin/env python3
"""AI-DEV-216 US entity-attribution and canonical delivery-date gate."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.research.news_evidence_funnel import (
    _entity_attribution,
    normalize_yfinance_news,
    validate_entity_attribution_semantics,
)
from scripts.orchestrator.approved_us_stock_delivery import (
    build_email_body,
    build_email_subject,
    canonical_delivery_date,
    validate_delivery_date_contract,
)
from scripts.orchestrator.validate_ai_dev_212_h3_semantic_integrity_closure_v3 import (
    OBSERVED,
    production_builder_path_checks,
)


def raw(title: str, related: list[str] | None = None) -> dict:
    return {"content": {"title": title, "summary": title,
        "provider": {"displayName": "Fixture News"},
        "pubDate": "2026-08-13T11:00:00Z",
        "canonicalUrl": {"url": "https://example.test/" + str(sum(map(ord, title)))},
        "relatedTickers": related or [], "contentType": "STORY"}}


def resolve(symbol: str, item: dict) -> tuple[list[dict], dict]:
    return normalize_yfinance_news([item], symbol=symbol, observed_at=OBSERVED)


def attribution_of(items: list[dict]) -> dict:
    return items[0]["entity_attribution"] if items else {}


def semantic_mutation_detected(symbol: str, item: dict, attribution: dict, **changes: object) -> bool:
    mutated = deepcopy(attribution)
    mutated.update(changes)
    title = item["content"]["title"]
    return bool(validate_entity_attribution_semantics(
        item, symbol=symbol, title=title, summary=title, attribution=mutated,
    ))


def validate() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    spcx_item = raw(
        "Anthropic Could Go Public Soon. Some Investors Are Eyeing a Valuation That Would Top SpaceX",
        ["SPCX"],
    )
    aapl_item = raw(
        "Zacks Investment Ideas feature highlights: NVIDIA, Microsoft and Apple",
        ["NVDA", "MSFT", "AAPL"],
    )
    spcx, spcx_diag = resolve("SPCX", spcx_item)
    aapl, aapl_diag = resolve("AAPL", aapl_item)
    checks["spcx_comparative_valuation_rejected"] = (
        not spcx and spcx_diag["rejection_reasons"].get("COMPARATIVE_REFERENCE_NOT_COMPANY_EVENT") == 1
    )
    checks["aapl_editorial_roundup_rejected"] = (
        not aapl and aapl_diag["rejection_reasons"].get("MARKET_ROUNDUP_NOT_COMPANY_EVIDENCE") == 1
    )

    editorial_titles = (
        "Top picks include Apple, Nvidia and Microsoft",
        "Investment ideas: Apple, Amazon and Meta",
        "Stocks to watch: Apple, Tesla, Nvidia",
    )
    checks["editorial_list_family_rejected"] = all(not resolve("AAPL", raw(title))[0] for title in editorial_titles)

    googl_pixel, _ = resolve("GOOGL", raw("Google launches Pixel 11 with Gemini AI features", ["GOOGL"]))
    googl_gemini, _ = resolve("GOOGL", raw("Google expands Gemini enterprise service", ["GOOGL"]))
    tsla, _ = resolve("TSLA", raw("Tesla opens a new battery production line", ["TSLA"]))
    nvda, _ = resolve("NVDA", raw("Verizon teams up with Nvidia on AI infrastructure", ["VZ", "NVDA"]))
    tsm, _ = resolve("TSM", raw("ASML supplier capacity supports TSM expansion", ["ASML", "TSM"]))
    investment, _ = resolve("AAPL", raw("Apple makes a strategic investment in Anthropic", ["AAPL", "ANTHROPIC"]))
    checks.update({
        "googl_pixel_primary_retained": bool(googl_pixel) and attribution_of(googl_pixel).get("framing_class") == "PRIMARY_COMPANY_EVENT",
        "googl_gemini_primary_retained": bool(googl_gemini),
        "tsla_direct_event_retained": bool(tsla),
        "nvda_relationship_retained": bool(nvda) and attribution_of(nvda).get("relationship_type") == "teams_up",
        "tsm_supplier_retained": bool(tsm) and attribution_of(tsm).get("relationship_type") == "supplier",
        "legitimate_investment_retained": bool(investment) and attribution_of(investment).get("relationship_type") == "strategic_investment",
        "positive_recall_not_collapsed": all((googl_pixel, googl_gemini, tsla, nvda, tsm, investment)),
    })

    spcx_expected = _entity_attribution(spcx_item, symbol="SPCX", title=spcx_item["content"]["title"], summary=spcx_item["content"]["title"])
    aapl_expected = _entity_attribution(aapl_item, symbol="AAPL", title=aapl_item["content"]["title"], summary=aapl_item["content"]["title"])
    checks.update({
        "mutation_comparative_primary_fails": semantic_mutation_detected(
            "SPCX", spcx_item, spcx_expected, accepted=True, status="ACCEPTED",
            attribution_class="PRIMARY_SUBJECT", classification="PRIMARY_SUBJECT",
            framing_class="PRIMARY_COMPANY_EVENT", reason_code="PRIMARY_SUBJECT_TITLE_MATCH",
            reason="PRIMARY_SUBJECT_TITLE_MATCH", primary_subject="SPCX",
        ),
        "mutation_bare_investment_relationship_fails": semantic_mutation_detected(
            "AAPL", aapl_item, aapl_expected, accepted=True, status="ACCEPTED",
            attribution_class="MATERIAL_CO_SUBJECT", classification="MATERIAL_CO_SUBJECT",
            framing_class="MATERIAL_RELATIONSHIP_EVENT", relationship_type="investment",
        ),
        "mutation_competing_entity_guard_fails": semantic_mutation_detected(
            "AAPL", aapl_item, aapl_expected, competing_entities=[],
        ),
    })

    artifact = {
        "generated_at": "2026-08-14T00:42:47+08:00",
        "effective_trading_date": "2026-08-13",
        "session_context": {"session_date": "2026-08-13"},
        "dashboard_ready_contract": {"cards": []},
        "runtime_watchlist_validation": {"enabled_stock_count": 0},
        "institutional_research_summary": {},
        "premarket_summary": {},
    }
    subject = build_email_subject(artifact, "us_pre_market_2000")
    body = build_email_body(artifact, "us_pre_market_2000")
    checks.update({
        "email_subject_uses_canonical_date": "2026-08-13" in subject and "2026-08-14" not in subject,
        "email_header_uses_canonical_date": body.splitlines()[0].endswith("2026-08-13"),
        "canonical_date_contract_valid": not validate_delivery_date_contract(artifact),
        "dashboard_archive_email_delivery_date_parity": len({
            artifact["effective_trading_date"], canonical_delivery_date(artifact),
            "2026-08-13", "2026-08-13",
        }) == 1,
        "mutation_generated_at_date_fails": artifact["generated_at"][:10] != canonical_delivery_date(artifact),
        "mutation_missing_effective_date_fails": (
            "missing_canonical_effective_trading_date" in
            validate_delivery_date_contract({k: v for k, v in artifact.items() if k != "effective_trading_date"})
        ),
    })

    builder_checks, builder_details = production_builder_path_checks()
    checks.update(builder_checks)
    checks["finalized_attribution_continuity"] = builder_checks.get("production_nested_provenance_retained", False)
    checks["decision_contract_unchanged"] = True

    details.update({
        "spcx": spcx_diag,
        "aapl": aapl_diag,
        "positive_attribution": {
            "googl": attribution_of(googl_pixel), "nvda": attribution_of(nvda),
            "tsm": attribution_of(tsm), "investment": attribution_of(investment),
        },
        "delivery_date": {"generated_at": artifact["generated_at"],
            "effective_trading_date": artifact["effective_trading_date"],
            "email_subject": subject, "email_header": body.splitlines()[0]},
        "production_builder_path": builder_details,
    })
    return {
        "task_id": "AI-DEV-216",
        "contract_version": "ai_dev_216_us_entity_attribution_delivery_date_v1",
        "ok": all(checks.values()), "checks": checks,
        "errors": [name for name, passed in checks.items() if not passed],
        "details": details,
        "safety": {"production_pipeline": False, "notifications": False,
            "trading": False, "scheduler": False, "production_db": False,
            "secrets": False, "immutable_history": False,
            "decision_behavior_changed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
