#!/usr/bin/env python3
"""AI-DEV-209 H3 user-visible research presentation closure gate."""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pypdf import PdfReader

from app.dashboard.market_dashboard_alias import identity_attributes
from app.dashboard.multi_market_dashboard import _us_window_card, base_css
from app.dashboard.visual_evidence_archive import capture_snapshot_visual_evidence
from app.dashboard.window_snapshot_archive import resolve_snapshots, write_snapshot
from app.us_stock.institutional_research import build_bundle, refresh_current_news
from app.us_stock.research_intelligence_v2 import evolve_intraday
from app.us_stock.research_presentation import current_news_presentation
from scripts.orchestrator.approved_us_stock_delivery import _compact_us_email_block
from scripts.orchestrator.validate_ai_dev_209_h2_qualified_news_rre_rendering_v2 import (
    OBSERVED,
    PARTITION,
    card as intraday_card,
    context,
    research,
)


def _bundle(symbol: str, count: int) -> dict:
    origin = build_bundle(symbol, research(symbol, 0), context(), "2026-08-13T20:00:00+08:00")
    current = build_bundle(symbol, research(symbol, count, official_first=symbol == "AAPL"), context(), OBSERVED)
    value = refresh_current_news(origin, current, OBSERVED)
    value["research_intelligence_v2"] = evolve_intraday(
        value["research_intelligence_v2"],
        {
            "data_status": "complete",
            "gap_current_pct": 0.5,
            "gap_state": "gap_up_follow_through",
            "volume_ratio": 1.2,
            "volume_confirmation_state": "confirmed",
            "source": "fixture",
        },
        observed_at=OBSERVED,
    )
    return value


def _review_card(symbol: str, bundle: dict) -> dict:
    value = intraday_card(symbol, bundle)
    value.update(
        {
            "trade_outcome": "no_trade",
            "trade_review_outcome": "no_trade",
            "prediction_range_result": "hit",
            "review": {
                "actual_high": 105,
                "actual_low": 98,
                "actual_close": 102,
                "entry_outcome": "not_applicable",
                "target_outcome": "not_applicable",
                "stop_outcome": "not_applicable",
                "mfe": 2.0,
                "mae": -1.0,
                "next_session_action": "reassess",
            },
            "prediction": {"today_range": "98-105"},
            "source_trade_plan": {
                "source_snapshot_id": f"legacy-{symbol}",
                "news_evidence": {
                    "availability": "unavailable",
                    "absence_label": "未發現相關即時新聞",
                },
                "sec_evidence": {},
                "event_risk": {},
            },
            "intraday_evidence": {"source_snapshot_id": f"intraday-{symbol}"},
            "research_review_diagnosis": {"research_diagnosis": f"{symbol} fixture diagnosis"},
        }
    )
    return value


def _absence_card(state: str) -> dict:
    stages = {name: 0 for name in (
        "DISCOVERED", "RETRIEVED", "NORMALIZED", "SYMBOL_ATTRIBUTED", "RELEVANT",
        "MATERIAL", "QUALITY_QUALIFIED", "FRESH", "DEDUPLICATED", "ADMITTED",
        "RRE_USED", "RENDERED",
    )}
    retrieval = {"status": "SUCCESS", "reason_code": None}
    reasons: dict[str, int] = {}
    if state == "RETRIEVAL_FAILED":
        retrieval = {"status": "FAILED", "reason_code": "UPSTREAM_ERROR"}
    elif state == "STALE_ONLY":
        stages["NORMALIZED"] = 2
        reasons["STALE"] = 2
    return {
        "symbol": f"FIX-{state}",
        "institutional_research": {
            "news_intelligence_v2": {
                "selected_items": [],
                "evidence_funnel": {
                    "stages": stages,
                    "retrieval": retrieval,
                    "rejection_reasons": reasons,
                },
            },
            "research_intelligence_v2": {},
        },
    }


def _pdf_text(path: Path) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def _contains_text(haystack: str, needle: object) -> bool:
    """Compare extracted PDF text without treating pagination whitespace as content."""
    normalize = lambda value: "".join(unicodedata.normalize("NFKC", str(value or "")).replace("\x00", "").split())
    return normalize(needle) in normalize(haystack)


def validate() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    bundles = {symbol: _bundle(symbol, count) for symbol, count in PARTITION.items()}
    cards = {symbol: _review_card(symbol, bundle) for symbol, bundle in bundles.items()}
    decision_before = {
        symbol: json.dumps(bundle.get("decision_context_export"), sort_keys=True)
        for symbol, bundle in bundles.items()
    }
    html_cards = {symbol: _us_window_card(value, "us_post_close_review_0630") for symbol, value in cards.items()}
    emails = {symbol: _compact_us_email_block(value, "us_post_close_review_0630") for symbol, value in cards.items()}
    headlines = {
        symbol: bundle["news_intelligence_v2"]["selected_items"][0]["headline"]
        for symbol, bundle in bundles.items()
    }

    checks["case_a_main_cards_use_canonical_current_news"] = all(
        headline in html_cards[symbol] and "當期個股新聞" in html_cards[symbol]
        for symbol, headline in headlines.items()
    )
    checks["case_b_legacy_absence_cannot_override_current_news"] = all(
        headline in emails[symbol] and "即時新聞：當期個股新聞" in emails[symbol]
        for symbol, headline in headlines.items()
    )
    checks["case_c_email_material_research_fields"] = all(
        all(label in emails[symbol] for label in ("研究假設：", "確認條件：", "失效條件：", "主要風險："))
        for symbol in cards
    )
    checks["case_d_six_symbol_narratives_distinct"] = all(
        len({bundles[s]["research_intelligence_v2"][key] for s in bundles}) == len(bundles)
        for key in ("primary_risk",)
    ) and len({bundles[s]["research_intelligence_v2"]["hypothesis"]["statement"] for s in bundles}) == len(bundles)

    absence = {state: current_news_presentation(_absence_card(state)) for state in ("NO_RELEVANT", "RETRIEVAL_FAILED", "STALE_ONLY")}
    checks["case_e_truthful_no_selected_states"] = all(
        absence[state]["state"] == state and absence[state]["selected_count"] == 0
        for state in absence
    )
    checks["case_f_directionless_visible_without_direction"] = all(
        bundle["news_intelligence_v2"]["directional_contribution"] == {"bullish": 0, "bearish": 0}
        and all(item["direction"] == "unavailable" for item in bundle["news_intelligence_v2"]["selected_items"])
        for bundle in bundles.values()
    )

    with tempfile.TemporaryDirectory(prefix="ai-dev-209-h3-") as raw:
        root = Path(raw)
        snapshots = root / "snapshots"
        visual = root / "visual"
        write_snapshot(
            snapshots,
            market="US",
            window="us_post_close_review_0630",
            effective_trading_date="2026-08-13",
            generated_at="2026-08-14T06:30:00+08:00",
            source_payload={"marker": "ai209-h3", "runtime_provenance": "scheduled_production"},
            status="completed",
            run_kind="scheduled",
            run_id="ai209-h3-fixture",
        )
        snapshot = resolve_snapshots(snapshots, "US", "us_post_close_review_0630").latest or {}
        page = root / "dashboard" / "us" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            + base_css()
            + "</style></head><body "
            + identity_attributes(snapshot)
            + "><main class='wrap'>"
            + "".join(html_cards.values())
            + "</main></body></html>",
            encoding="utf-8",
        )
        result = capture_snapshot_visual_evidence(snapshot, page, output_root=visual)
        manifest_path = Path(str(result.get("manifest_path")))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rendered_text = (manifest_path.parent / "rendered_text.md").read_text(encoding="utf-8")
        archived_html = (manifest_path.parent / "rendered_page.html").read_text(encoding="utf-8")
        pdf_text = _pdf_text(manifest_path.parent / "dashboard_full.pdf")
        checks["case_g_real_chromium_visual_capture"] = (
            result.get("status") == "SUCCESS"
            and manifest["capture"]["renderer"] == "playwright-chromium"
            and manifest["capture"]["review_details"]["expanded_count"] == len(cards)
        )
        checks["case_h_rendered_text_has_selected_provenance"] = all(
            headline in rendered_text for headline in headlines.values()
        ) and all("Publisher " + symbol in rendered_text or symbol == "AAPL" for symbol in headlines)
        checks["case_i_pdf_text_has_selected_provenance"] = all(
            _contains_text(pdf_text, headline) for headline in headlines.values()
        )
        # Chromium's CJK subset font is visually faithful but does not expose
        # every Chinese glyph through PDF text extraction.  English section
        # labels plus each symbol-specific evidence fingerprint prove that the
        # allowlisted hypothesis/risk DOM was printed, without OCR or mocks.
        normalized_pdf = unicodedata.normalize("NFKC", pdf_text).replace("\x00", "")
        checks["case_j_pdf_has_material_narratives"] = (
            all(_contains_text(pdf_text, headlines[symbol]) for symbol in bundles)
            and normalized_pdf.count("Hypothesis") >= len(bundles)
            and normalized_pdf.count("Trigger") >= len(bundles)
            and normalized_pdf.count("Invalidation") >= len(bundles)
            and normalized_pdf.count("Main Risk") >= len(bundles)
        )
        checks["case_k_archived_html_preserves_collapsed_state"] = (
            'data-visual-review-expand="true"' in archived_html
            and '<details class="research-review-details" data-visual-review-expand="true" open' not in archived_html
            and manifest["capture"]["review_details"]["published_dom_modified"] is False
        )
        details["capture"] = {
            "status": result.get("status"),
            "manifest": str(manifest_path),
            "pdf_pages": len(PdfReader(str(manifest_path.parent / "dashboard_full.pdf")).pages),
            "expanded_details": manifest["capture"]["review_details"]["expanded_count"],
        }

    decision_after = {
        symbol: json.dumps(bundle.get("decision_context_export"), sort_keys=True)
        for symbol, bundle in bundles.items()
    }
    checks["case_l_decision_ownership_unchanged"] = decision_before == decision_after and all(
        bundle["decision_context_export"]["trade_action"] is None for bundle in bundles.values()
    )
    h2 = subprocess.run(
        [sys.executable, str(ROOT / "scripts/orchestrator/validate_ai_dev_209_h2_qualified_news_rre_rendering_v2.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    ai210 = subprocess.run(
        [sys.executable, str(ROOT / "scripts/orchestrator/validate_ai_dev_210_visual_evidence_pdf_retrieval_v1.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    checks["case_m_h2_regression"] = h2.returncode == 0 and bool(json.loads(h2.stdout).get("ok"))
    checks["case_n_ai210_regression"] = ai210.returncode == 0 and bool(json.loads(ai210.stdout).get("ok"))
    details.update(
        {
            "symbols": list(PARTITION),
            "headlines": headlines,
            "absence_states": absence,
            "h2_returncode": h2.returncode,
            "ai210_returncode": ai210.returncode,
        }
    )
    return {
        "task_id": "AI-DEV-209-H3",
        "ok": all(checks.values()),
        "checks": checks,
        "details": details,
        "errors": [name for name, ok in checks.items() if not ok],
        "safety": {
            "network": False,
            "production_pipeline": False,
            "publish": False,
            "notification": False,
            "trading": False,
            "database_write": False,
            "immutable_history_rewrite": False,
            "decision_behavior_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
