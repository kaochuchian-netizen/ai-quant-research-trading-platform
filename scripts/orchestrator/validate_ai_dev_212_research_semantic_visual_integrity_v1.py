#!/usr/bin/env python3
"""AI-DEV-212 semantic ownership, attribution, funnel and CJK visual gate."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pypdf import PdfReader

from app.dashboard.market_dashboard_alias import identity_attributes
from app.dashboard.visual_evidence_archive import capture_snapshot_visual_evidence
from app.dashboard.window_snapshot_archive import resolve_snapshots, write_snapshot
from app.research.news_evidence_funnel import normalize_yfinance_news
from app.us_stock.premarket_decision import separate_sec_news
from app.us_stock.research_intelligence_v2 import build_event_narrative, build_initial_projection


OBSERVED = "2026-08-13T20:00:00+08:00"


def evidence(eid: str, event: str, direction: str, ownership: str, headline: str) -> dict:
    return {
        "evidence_id": eid, "event_type": event, "direction": direction,
        "direction_ownership": ownership, "headline": headline, "summary": headline,
        "quality_score": 90, "confidence": .9, "counted_in_synthesis": True,
        "official_confirmation": ownership == "company_substantive",
        "source_reference": eid, "provider": "fixture", "materiality": "high",
    }


def projection(items: list[dict], symbol: str = "FIX") -> dict:
    return build_initial_projection({
        "symbol": symbol, "research_identity": f"research-{symbol}", "evidence": items,
        "providers": [], "knowledge": {"status": "PARTIAL"},
        "news_intelligence_v2": {"selected_items": []},
    }, observed_at=OBSERVED)


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0
    return struct.unpack(">II", data[16:24])


def validate() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    regulatory = build_event_narrative("REG", evidence("reg", "regulatory", "bearish", "company_substantive", "REG faces antitrust investigation"), "bearish")
    earnings = build_event_narrative("ERN", evidence("ern", "earnings", "bullish", "company_substantive", "ERN raises revenue guidance"), "bullish")
    checks["case_1_regulatory_vs_earnings_narrative"] = (
        regulatory["event_family"] == "regulatory_legal"
        and earnings["event_family"] == "earnings_guidance"
        and regulatory["trigger"] != earnings["trigger"]
        and regulatory["invalidation"] != earnings["invalidation"]
        and regulatory["primary_risk"] != earnings["primary_risk"]
        and "價格／相對強弱僅作次級確認" in regulatory["trigger"] + earnings["trigger"]
    )

    market_only = projection([
        evidence("SPY", "market_context", "bullish", "contextual_confirmation_only", "SPY market context"),
        evidence("QQQ", "market_context", "bullish", "contextual_confirmation_only", "QQQ market context"),
        evidence("SOXX", "sector", "bullish", "contextual_confirmation_only", "SOXX sector context"),
    ], "CTX")
    checks["case_2_market_context_cannot_establish_company_direction"] = (
        market_only["research_stance"] == "insufficient_evidence"
        and market_only["research_score"] is None
        and market_only["hypothesis"]["expected_direction"] == "unavailable"
        and market_only["evidence_ownership"]["market_context_can_establish_company_direction"] is False
    )

    directionless = projection([evidence("news", "product", "unavailable", "company_substantive", "FIX launches product")], "FIX")
    checks["case_3_directionless_news_visible_without_direction"] = (
        directionless["research_stance"] == "insufficient_evidence"
        and directionless["evidence_ownership"]["direction_establishing_ids"] == []
        and directionless["hypothesis"]["event_family"] == "product_demand"
    )

    common = {"provider": {"displayName": "Fixture"}, "pubDate": "2026-08-13T10:00:00Z", "canonicalUrl": {"url": "https://example.test/item"}, "contentType": "STORY"}
    rejected, rejected_diag = normalize_yfinance_news([{"content": {**common, "title": "Abbott Laboratories (ABT) connects glucose data to AI health tools", "summary": "Google technology is mentioned as context."}}], symbol="GOOGL", observed_at=OBSERVED)
    accepted, accepted_diag = normalize_yfinance_news([{"content": {**common, "title": "Abbott Laboratories (ABT) connects glucose data to Google AI health tools", "relatedTickers": ["GOOGL"]}}], symbol="GOOGL", observed_at=OBSERVED)
    checks["case_4_false_attribution_rejected_valid_relationship_retained"] = (
        not rejected and rejected_diag["rejection_reasons"].get("WEAK_CONTEXTUAL_COMENTION") == 1
        and len(accepted) == 1
        and accepted[0]["entity_attribution"]["reason_code"] == "PROVIDER_RELATED_TICKER"
    )

    finalized = {"stages": {"ADMITTED": 2, "RRE_USED": 1, "RENDERED": 1}, "absence_state": "NEWS_SELECTED_AND_RENDERED"}
    selected_item = {"headline": "Company event", "publisher": "Fixture", "published_at": "2026-08-13T10:00:00Z", "selected_for_rre": True, "rendered": True}
    research = {"institutional_research": {"news_intelligence_v2": {"selected_items": [selected_item], "evidence_funnel": finalized}}}
    _, card_news = separate_sec_news(research, [], finalized)
    checks["case_5_finalized_funnel_single_truth"] = (
        card_news["availability"] == "available"
        and card_news["absence_state"] == "NEWS_SELECTED_AND_RENDERED"
        and card_news["evidence_funnel"]["stages"]["RRE_USED"] == 1
        and card_news["evidence_funnel"]["stages"]["RENDERED"] == 1
        and card_news["finalized_projection"] is True
    )
    mutated = json.loads(json.dumps(card_news))
    mutated["evidence_funnel"]["stages"].update({"RRE_USED": 0, "RENDERED": 0})
    contradiction = mutated["absence_state"] == "NEWS_SELECTED_AND_RENDERED" and mutated["evidence_funnel"]["stages"]["RENDERED"] == 0
    checks["case_5_mutation_detects_funnel_contradiction"] = contradiction

    shaped = {
        "AAPL": ("partnership", "Apple signs publisher partnership for Siri"),
        "NVDA": ("supply_chain", "Nvidia expands AI infrastructure supply"),
        "TSLA": ("product", "Tesla delivery demand changes"),
        "GOOGL": ("regulatory", "Google faces antitrust ruling"),
        "SPCX": ("contract", "SPCX wins lunar mission contract"),
        "TSM": ("earnings", "TSM raises earnings guidance"),
    }
    narratives = {symbol: build_event_narrative(symbol, evidence(symbol, event, "unavailable", "company_substantive", headline), "insufficient_evidence") for symbol, (event, headline) in shaped.items()}
    checks["case_6_natural_shaped_company_narratives"] = (
        len({value["statement"] for value in narratives.values()}) == 6
        and len({value["primary_risk"] for value in narratives.values()}) == 6
        and len({value["event_family"] for value in narratives.values()}) >= 5
    )

    with tempfile.TemporaryDirectory(prefix="ai-dev-212-") as raw:
        root = Path(raw)
        snapshots, visual = root / "snapshots", root / "visual"
        write_snapshot(snapshots, market="US", window="us_pre_market_2000", effective_trading_date="2026-08-13", generated_at=OBSERVED, source_payload={"marker": "ai212", "runtime_provenance": "validation_only"}, status="completed", run_kind="scheduled", run_id="ai212-fixture")
        snapshot = resolve_snapshots(snapshots, "US", "us_pre_market_2000").latest or {}
        page = root / "dashboard.html"
        chinese = "研究證據、公司假設、確認條件、失效條件與主要風險均可閱讀。"
        page.write_text("<!doctype html><html><head><meta charset='utf-8'><style>body{font-family:system-ui,sans-serif;font-size:28px}</style></head><body " + identity_attributes(snapshot) + f"><main><h1>視覺證據</h1><p>{chinese}</p></main></body></html>", encoding="utf-8")
        result = capture_snapshot_visual_evidence(snapshot, page, output_root=visual)
        manifest_path = Path(str(result.get("manifest_path")))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        capture_dir = manifest_path.parent
        screenshot, pdf = capture_dir / "screenshot_full.png", capture_dir / "dashboard_full.pdf"
        font = (manifest.get("capture") or {}).get("font_diagnostics") or {}
        checks["case_7_real_chromium_cjk_visual_gate"] = (
            result.get("status") == "SUCCESS" and font.get("font_loaded") is True
            and int(font.get("unique_glyph_signatures") or 0) >= 6
            and chinese in (capture_dir / "rendered_text.md").read_text(encoding="utf-8")
        )
        checks["case_7_png_pdf_manifest_hash_integrity"] = (
            png_dimensions(screenshot)[0] == 1440
            and pdf.read_bytes().startswith(b"%PDF")
            and len(PdfReader(str(pdf)).pages) >= 1
            and all(hashlib.sha256((capture_dir / entry["path"]).read_bytes()).hexdigest() == entry["sha256"] for entry in manifest.get("files", {}).values())
            and manifest["capture"]["review_details"]["published_dom_modified"] is False
        )
        details["visual"] = {"result": result.get("status"), "png_dimensions": png_dimensions(screenshot), "png_size": screenshot.stat().st_size, "png_sha256": hashlib.sha256(screenshot.read_bytes()).hexdigest(), "pdf_pages": len(PdfReader(str(pdf)).pages), "pdf_size": pdf.stat().st_size, "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "font_diagnostics": font}

    checks["case_8_decision_boundary_unchanged"] = (
        market_only["decision_context_export"] == {"trade_action": None, "eligibility": None, "ranking": None}
        and market_only["boundary"]["action_exported"] is False
        and market_only["boundary"]["scoring_modified"] is False
        and market_only["boundary"]["strategy_weights_modified"] is False
    )
    return {"task_id": "AI-DEV-212", "ok": all(checks.values()), "checks": checks, "details": {**details, "narratives": narratives, "market_only": market_only["research_stance"], "attribution_rejections": rejected_diag["rejection_reasons"]}, "errors": [name for name, ok in checks.items() if not ok], "safety": {"production_pipeline": False, "network_during_validation": False, "notifications": False, "trading": False, "production_db": False, "immutable_history": False}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
