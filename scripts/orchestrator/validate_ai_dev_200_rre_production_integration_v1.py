#!/usr/bin/env python3
"""Deterministic semantic gate for AI-DEV-200 RRE production integration."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import _decision_intelligence_v4_html, render_tw_window_report
from app.reports.decision_intelligence_v4 import project_decision_intelligence_v4
from app.reports.tw_decision_intelligence_v2 import (
    compact_tw_v2_lines,
    validate_tw_decision_intelligence_v2,
)
from app.runtime.operations_provenance import build_operations_provenance
from scripts.orchestrator.tw_four_window_validation_fixture import payloads
from scripts.orchestrator.validate_ai_dev_198_tw_decision_intelligence_v2 import _enrich


def _fixtures() -> dict:
    fixtures = _enrich(payloads())
    for window, payload in fixtures.items():
        payload["generated_at"] = "2026-07-31T07:00:00+08:00"
        payload["effective_trading_date"] = "2026-07-31"
        cards = payload.get("cards") or []
        for card in cards:
            symbol = str(card.get("symbol") or card.get("stock_id"))
            card["data_gaps"] = ["CHIP_UNAVAILABLE", "GAP_UNAVAILABLE"]
            if symbol == "2330":
                card["adr_context"] = "TSM ADR：上漲 7.64%"
                card["plan_status"] = "watch"
                card["action"] = "觀察等待"
            if symbol == "4743":
                card.update({
                    "news_direction": "bullish",
                    "news_evidence": {
                        "confidence": {"score": 72},
                        "evidence": [{
                            "headline": "新藥里程碑取得進展",
                            "publisher": "公司重大訊息",
                            "published_at": "2026-07-31T06:30:00+08:00",
                            "direction": "bullish", "source_tier": 1,
                            "materiality": "high", "source_url": "fixture:4743",
                        }],
                    },
                    "plan_status": "no_trade", "action": "暫不操作",
                })
    return fixtures


def validate() -> dict:
    errors: list[str] = []
    details: dict = {"windows": {}, "negative_tests": {}}
    fixtures = _fixtures()
    identities = {}
    for window, payload in fixtures.items():
        projection = project_decision_intelligence_v4("TW", window, payload)
        tw = projection.get("tw_decision_intelligence_v2") or {}
        research = projection.get("research_reasoning_projection") or {}
        semantic = validate_tw_decision_intelligence_v2(tw)
        errors.extend(f"{window}:{item}" for item in semantic)
        cards = payload.get("cards") or []
        notes = research.get("research_notes") or []
        if len(notes) != len(cards):
            errors.append(f"{window}:research_card_count")
        if any(note.get("generated_by") != "research_reasoning_engine_v1" for note in notes):
            errors.append(f"{window}:legacy_note")
        if any(not all(isinstance(note.get(key), list) for key in ("supporting", "opposing", "missing")) for note in notes):
            errors.append(f"{window}:evidence_render_contract")
        if any(not (note.get("hypothesis") or {}).get("expected_trigger") or not (note.get("hypothesis") or {}).get("invalidation") for note in notes):
            errors.append(f"{window}:hypothesis")
        if any(not note.get("counter_argument") for note in notes):
            errors.append(f"{window}:counter_argument")
        if any(note.get("decision_modified") is not False for note in notes):
            errors.append(f"{window}:decision_boundary")
        if research.get("research_first_pipeline") is not True or research.get("decision_is_read_only_consumer") is not True:
            errors.append(f"{window}:pipeline_order")
        if projection.get("research_reasoning_identity") != tw.get("research_reasoning_identity"):
            errors.append(f"{window}:projection_identity")
        html = _decision_intelligence_v4_html("TW", window, payload)
        for marker in ("tw-rre-production", "逐股機構研究筆記", "支持證據", "反對證據", "未知／缺口", "研究假設", "成立條件", "失效條件", "如果判斷錯誤"):
            if marker not in html:
                errors.append(f"{window}:html:{marker}")
        if "{'" in html or '"evidence_id"' in html:
            errors.append(f"{window}:raw_representation")
        public_html = render_tw_window_report(window, payload)
        research_position = public_html.find("tw-rre-production")
        first_card_position = public_html.find("window-stock-card")
        if research_position < 0 or (first_card_position >= 0 and research_position > first_card_position):
            errors.append(f"{window}:public_research_not_primary")
        if public_html.count('data-generated-by="research_reasoning_engine_v1"') != len(cards):
            errors.append(f"{window}:public_research_note_count")
        lines = compact_tw_v2_lines(tw)
        if len(lines) != 4 or "研究" not in lines[0] or "最佳研究" not in lines[1]:
            errors.append(f"{window}:channel_preview")
        operations = build_operations_provenance(
            market="TW", window=window, runtime_status="controlled_no_send",
            runtime_trading_date="2026-07-31",
            snapshot={"payload": payload, "snapshot_id": payload["snapshot_id"], "revision": 1},
            public_sync={}, email_result="controlled_no_send", line_result="controlled_no_send",
        )
        op_tw = operations.get("tw_decision_intelligence_v2") or {}
        if op_tw.get("research_reasoning_identity") != tw.get("research_reasoning_identity"):
            errors.append(f"{window}:operations_identity")
        notes_by_symbol = {note["symbol"]: note for note in notes}
        if "2330" in notes_by_symbol and not any("ADR" in item and "7.64" in item for item in notes_by_symbol["2330"]["supporting"]):
            errors.append(f"{window}:2330_adr_reasoning")
        if "4743" in notes_by_symbol:
            note = notes_by_symbol["4743"]
            if not any("新聞" in item and "新藥" in item for item in note["supporting"]):
                errors.append(f"{window}:4743_news_reasoning")
            if note.get("decision_category") == "BUY_CANDIDATE":
                errors.append(f"{window}:research_promoted_decision")
        expected_update = {
            "pre_open_0700": "建立今日研究假設",
            "intraday_1305": "盤中檢查",
            "pre_close_1335": "收盤前判斷",
            "post_close_1500": "盤後檢討",
        }[window]
        if any(expected_update not in note["window_update"]["state"] for note in notes):
            errors.append(f"{window}:window_research_update")
        if window == "post_close_1500":
            hooks = (research.get("rre_projection") or {}).get("review_hooks") or {}
            if hooks.get("automatic_learning") is not False or "hypothesis" not in (hooks.get("dimensions") or []):
                errors.append("post_close_1500:review_hooks")
        identities[window] = research.get("production_research_identity")
        details["windows"][window] = {
            "research_identity": research.get("production_research_identity"),
            "rre_identity": research.get("research_reasoning_identity"),
            "note_count": len(notes),
            "brief": research.get("morning_or_window_brief"),
        }

    corrupt = project_decision_intelligence_v4("TW", "pre_open_0700", fixtures["pre_open_0700"])
    corrupt = copy.deepcopy(corrupt["tw_decision_intelligence_v2"])
    corrupt["research_reasoning_projection"]["research_notes"][0]["decision_modified"] = True
    negative = validate_tw_decision_intelligence_v2(corrupt)
    details["negative_tests"]["decision_mutation"] = negative
    if not any("decision_boundary" in item for item in negative):
        errors.append("negative:decision_mutation")

    no_evidence = copy.deepcopy(fixtures["pre_open_0700"])
    for card in no_evidence["cards"]:
        card.update({
            "adr_context": "資料尚未取得", "news_evidence": {}, "news_direction": "unavailable",
            "technical_data": {"analysis_eligible": False, "history_bars": 5, "direction": "unavailable", "source": "fixture"},
            "sector_context": None, "fundamental_context": None, "macro_context": None,
            "data_gaps": ["INSUFFICIENT_HISTORY", "NEWS_UNAVAILABLE", "CHIP_UNAVAILABLE"],
        })
    empty_projection = project_decision_intelligence_v4("TW", "pre_open_0700", no_evidence)
    empty_notes = empty_projection["research_reasoning_projection"]["research_notes"]
    details["negative_tests"]["missing_truthfulness"] = [note["research_summary"] for note in empty_notes[:2]]
    if any(note["conclusion"] not in {"insufficient_evidence", "mixed"} and not note["supporting"] and not note["opposing"] for note in empty_notes):
        errors.append("negative:invented_conclusion")
    if any(not note["missing"] for note in empty_notes):
        errors.append("negative:missing_not_disclosed")

    details["identities"] = identities
    details["model_boundary"] = (
        project_decision_intelligence_v4("TW", "pre_open_0700", fixtures["pre_open_0700"])
        ["research_reasoning_projection"]["model_boundary"]
    )
    return {
        "ok": not errors,
        "validator": "validate_ai_dev_200_rre_production_integration_v1",
        "errors": sorted(set(errors)),
        "details": details,
        "safety": {
            "production_pipeline": False, "notification": False, "trading": False,
            "scheduler": False, "secrets": False, "archive_history": False,
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
