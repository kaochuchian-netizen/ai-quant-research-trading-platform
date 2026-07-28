#!/usr/bin/env python3
"""Deterministic AI-DEV-195 semantic and cross-channel validation bundle."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import _decision_intelligence_v4_html
from app.reports.daily_decision_experience import (
    build_daily_decision_experience,
    compact_decision_story,
    validate_daily_decision_experience,
)
from app.reports.decision_intelligence_v4 import (
    compact_summary,
    delivery_summary_lines,
    project_decision_intelligence_v4,
)
from app.runtime.operations_provenance import build_operations_provenance


def card(symbol: str = "2330", **overrides: object) -> dict:
    base = {
        "market": "TW", "symbol": symbol, "confidence": 62,
        "data_status": "complete", "freshness_status": "fresh",
        "source_name": "fixture_market_provider", "source_record_time": "2026-07-28T13:05:00+08:00",
        "market_data_as_of": "2026-07-28T13:05:00+08:00", "current_price": 100,
        "action_change_reason": "價格與風險證據支持目前觀察。", "missing_fields": [], "data_gaps": [],
        "technical_data": {
            "source": "canonical_daily_ohlcv", "source_timestamp": "2026-07-27T13:30:00+08:00",
            "freshness": "fresh", "analysis_eligible": True, "history_bars": 60,
            "required_bars": 20, "history_start": "2026-05-01", "history_end": "2026-07-27",
            "direction": "bullish",
        },
    }
    base.update(overrides)
    return base


def payload(window: str, cards: list[dict], **overrides: object) -> dict:
    key = {
        "pre_open_0700": "structured_pre_open_cards",
        "intraday_1305": "structured_intraday_cards",
        "pre_close_1335": "structured_pre_close_cards",
        "post_close_1500": "structured_review_cards",
    }[window]
    value = {
        "market": "TW", "window": window, "effective_trading_date": "2026-07-28",
        "generated_at": "2026-07-28T13:06:00+08:00", "source_data_time": "2026-07-28T13:05:00+08:00",
        "revision": 1, key: cards,
    }
    value.update(overrides)
    return value


def timeline(previous: str, current: str, window: str = "intraday_1305") -> list[dict]:
    return [
        {"symbol": "2330", "source_window": "pre_open_0700", "state": previous,
         "effective_date": "2026-07-28", "snapshot_id": "tw-0700", "source_snapshot_id": "tw-0700", "revision": 1},
        {"symbol": "2330", "source_window": window, "state": current,
         "effective_date": "2026-07-28", "snapshot_id": f"tw-{window}", "source_snapshot_id": f"tw-{window}", "revision": 1},
    ]


def run() -> dict:
    checks: dict[str, bool] = {}
    evidence: dict[str, object] = {}

    unchanged_payload = payload("intraday_1305", [card(lifecycle_timeline=timeline("watch", "watch"))])
    unchanged = build_daily_decision_experience("TW", "intraday_1305", unchanged_payload)
    checks["case_1_decision_unchanged"] = unchanged["change_from_previous_window"]["state"] == "UNCHANGED"

    downgraded_payload = payload("intraday_1305", [card(lifecycle_timeline=timeline("active", "watch"))])
    downgraded = build_daily_decision_experience("TW", "intraday_1305", downgraded_payload)
    checks["case_2_decision_downgraded"] = downgraded["change_from_previous_window"]["state"] == "DOWNGRADED"

    missing_payload = payload("intraday_1305", [card(
        data_status="partial", current_price=None, missing_fields=["session_volume"],
        data_gaps=["VOLUME_SOURCE_FAILED"], technical_data={}, confidence=38,
    )])
    missing = build_daily_decision_experience("TW", "intraday_1305", missing_payload)
    missing_records = missing["missing_data_impact"]["records"]
    checks["case_3_missing_critical_data"] = (
        missing["missing_data_impact"]["missing_is_neutral"] is False
        and any(item["status"] == "SOURCE_FAILED" for item in missing_records)
        and "session_volume" in missing["confidence_explanation"]["missing_inputs"]
    )

    stale_payload = payload("intraday_1305", [card(freshness_status="stale")])
    stale = build_daily_decision_experience("TW", "intraday_1305", stale_payload)
    checks["case_4_stale_evidence"] = (
        stale["source_freshness"]["has_stale"] is True
        and any(item["status"] == "STALE" for item in stale["missing_data_impact"]["records"])
    )

    projection = project_decision_intelligence_v4("TW", "intraday_1305", unchanged_payload)
    operations = build_operations_provenance(
        market="TW", window="intraday_1305", runtime_status="completed",
        runtime_trading_date="2026-07-28", snapshot={"payload": unchanged_payload, "revision": 1},
        public_sync={}, email_result="controlled_no_send", line_result="controlled_no_send",
    )
    html = _decision_intelligence_v4_html("TW", "intraday_1305", unchanged_payload)
    canonical_hash = projection["canonical_summary_hash"]
    checks["case_5_cross_channel_parity"] = (
        operations["canonical_daily_decision_hash"] == canonical_hash
        and canonical_hash in html
        and "目前行動" in compact_summary(projection, "email")
        and delivery_summary_lines(projection) == compact_decision_story(projection["canonical_decision_summary"])
    )

    no_prior_payload = payload("pre_open_0700", [card(current_price=None, lifecycle_timeline=[])], pre_open_summary={"top_opportunity_count": 0, "watch_only_count": 1, "no_trade_count": 0})
    no_prior = build_daily_decision_experience("TW", "pre_open_0700", no_prior_payload)
    checks["case_6_no_prior_window"] = no_prior["change_from_previous_window"]["state"] == "NO_PRIOR_STATE"

    revision_payload = copy.deepcopy(unchanged_payload)
    revision_payload["revision"] = 2
    revision = build_daily_decision_experience("TW", "intraday_1305", revision_payload)
    checks["case_7_same_day_revision"] = revision["artifact_revision"] == 2 and revision["effective_trading_date"] == "2026-07-28"

    foreign = card(symbol="AAPL", market="US", lifecycle_timeline=[])
    isolation_payload = payload("pre_open_0700", [card(current_price=None), foreign], pre_open_summary={})
    isolation = build_daily_decision_experience("TW", "pre_open_0700", isolation_payload)
    checks["case_8_tw_us_isolation"] = (
        isolation["card_count"] == 1
        and isolation["market_isolation"]["rejected_cross_market_card_count"] == 1
        and all(item["market"] == "TW" for item in isolation["evidence_summary"]["records"])
    )

    semantic_samples = [unchanged, downgraded, missing, stale, no_prior, revision, isolation]
    checks["semantic_contracts"] = all(not validate_daily_decision_experience(item) for item in semantic_samples)

    corrupt_missing = copy.deepcopy(missing)
    corrupt_missing["missing_data_impact"]["missing_is_neutral"] = True
    checks["negative_missing_as_neutral_rejected"] = "missing_data_must_not_be_neutral" in validate_daily_decision_experience(corrupt_missing)
    corrupt_channel = copy.deepcopy(projection["canonical_decision_summary"])
    corrupt_channel["current_action"] = "另一個 channel 自行改寫 action"
    checks["negative_channel_drift_rejected"] = "canonical_summary_hash_mismatch" in validate_daily_decision_experience(corrupt_channel)
    corrupt_future = copy.deepcopy(unchanged)
    corrupt_future["lifecycle_timeline"][0]["effective_date"] = "2026-07-29"
    checks["negative_future_previous_rejected"] = any(error.startswith("future_timeline_evidence") for error in validate_daily_decision_experience(corrupt_future))
    corrupt_market = copy.deepcopy(unchanged)
    corrupt_market["evidence_summary"]["records"][0]["market"] = "US"
    checks["negative_cross_market_evidence_rejected"] = any(error.startswith("cross_market_evidence") for error in validate_daily_decision_experience(corrupt_market))
    corrupt_stale = copy.deepcopy(stale)
    corrupt_stale["missing_data_impact"]["records"] = [item for item in corrupt_stale["missing_data_impact"]["records"] if item["status"] != "STALE"]
    checks["negative_stale_as_latest_rejected"] = "stale_not_disclosed" in validate_daily_decision_experience(corrupt_stale)

    evidence.update({
        "canonical_summary_hash": canonical_hash,
        "transition_cases": {"unchanged": unchanged["change_from_previous_window"], "downgraded": downgraded["change_from_previous_window"]},
        "missing_count": missing["missing_data_impact"]["count"],
        "stale_disclosed": stale["source_freshness"]["has_stale"],
        "channel_adapters": ["dashboard", "line", "email", "archive_projection", "operations"],
        "model_changes": {"strategy": False, "scoring": False, "ranking": False},
    })
    return {
        "ok": all(checks.values()), "task_id": "AI-DEV-195",
        "schema_version": "ai_dev_195_product_quality_validation_v1",
        "checks": checks, "evidence": evidence,
        "matrix": {"positive": 8, "negative": 5, "deterministic": True},
        "side_effects": {
            "production_pipeline": False, "notifications": False, "trading": False,
            "scheduler": False, "archive_history": False, "secrets": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
