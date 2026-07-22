#!/usr/bin/env python3
"""Deterministic AI-DEV-188 correctness and presentation contracts."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard.public_latest_sync import identity_parity
from app.dashboard.window_snapshot_archive import resolve_snapshots
from app.reports.canonical_outcomes import aggregate_us_post_close_review, normalize_review_card
from app.reports.presentation_normalization import (
    concise_news_summary, format_adr_context, format_market_time, format_timestamp,
    localize_enum, safe_public_text,
)


def _snapshot(root: Path, day: str, revision: int, admitted_at: str, snapshot_id: str) -> None:
    target = root / "tw/pre_close_1335" / day / f"revision-{revision:04d}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "window_snapshot_archive_v1", "market": "TW", "window": "pre_close_1335",
        "effective_trading_date": day, "generated_at": admitted_at, "revision_created_at": admitted_at,
        "admitted_at": admitted_at, "revision": revision, "snapshot_id": snapshot_id,
        "status": "complete", "admitted": True, "runtime_provenance": "scheduled_production",
        "admission_reason": "scheduled_production", "run_kind": "scheduled", "payload": {
            "generated_at": admitted_at, "market": "TW", "window": "pre_close_1335",
            "runtime_provenance": "scheduled_production", "fixture": False, "validation_only": False,
        },
    }
    target.write_text(json.dumps(payload), encoding="utf-8")


def checks() -> dict[str, bool]:
    legacy = {"symbol": "AAPL", "canonical_outcome": "hit", "review": {
        "range_covered": True, "actual_high": 10, "actual_low": 8, "actual_close": 9,
        "snapshot_ref": "snapshot.json",
    }}
    normalized = normalize_review_card(legacy)
    aggregate = aggregate_us_post_close_review([legacy])
    trade_hit = normalize_review_card({"symbol": "NVDA", "canonical_outcome": "hit", "review": {
        "range_covered": True, "actual_high": 12, "actual_low": 8, "actual_close": 11,
        "entry_triggered": True, "target_1_hit": True,
    }})
    unavailable_news = concise_news_summary({"news_summary": "新聞分析暫時無法取得", "news_source_class": "general_media", "predicted_direction": "no_trade"})
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        _snapshot(root, "2026-07-21", 9, "2026-07-22T14:00:00+08:00", "older-date-newer-mtime")
        _snapshot(root, "2026-07-22", 1, "2026-07-22T13:42:05+08:00", "newer-date")
        _snapshot(root, "2026-07-22", 2, "2026-07-22T13:43:05+08:00", "newer-revision")
        selected = resolve_snapshots(root, "TW", "pre_close_1335").latest or {}
    cases = {
        "latest_effective_date": selected.get("effective_trading_date") == "2026-07-22",
        "latest_revision": selected.get("revision") == 2,
        "notification_public_mismatch_detected": identity_parity(
            {"market": "TW", "window": "pre_close_1335", "effective_trading_date": "2026-07-22", "snapshot_id": "new", "revision": 1, "payload_hash": "new-hash"},
            {"market": "TW", "window": "pre_close_1335", "effective_trading_date": "2026-07-21", "snapshot_id": "old", "revision": 1, "payload_hash": "old-hash"},
        )["status"] == "failed_verification",
        "prediction_hit_trade_pending": normalized["prediction_range_result"] == "hit" and normalized["trade_outcome"] == "pending",
        "trade_hit_requires_target": trade_hit["trade_outcome"] == "hit",
        "separate_aggregate": aggregate["prediction_range_hit_count"] == 1 and aggregate["trade_pending_count"] == 1 and aggregate["trade_hit_count"] == 0,
        "news_unavailable_truthful": unavailable_news == {
            "direction": "無法判定", "status": "本批次未取得可用分析", "reason": "本批次未取得可用新聞分析",
            "strategy_impact": "不調整原技術／策略排序", "source_quality": "無法判定", "confidence": "無法判定",
        },
        "rr_localized": safe_public_text("reward/risk below 0.8 threshold").startswith("風險報酬比"),
        "adr_semantics": all(token in format_adr_context("change rate：5.55", strategy_action="no_trade") for token in ("TSM ADR", "上漲 5.55%", "最近一個美股交易日", "不改變目前無交易判斷")),
        "epoch_ns_not_raw": format_timestamp(1784730600000000000, reference_value="2026-07-22T15:01:00+08:00") == "2026-07-22 14:30:00",
        "date_only_honest": format_market_time("2026-07-22", time_kind="trading_date_only", trading_date="2026-07-22") == ("行情日期", "2026-07-22"),
        "invalid_timestamp_safe": format_timestamp("not-a-time") == "尚未取得",
        "enum_localized": localize_enum("cancel_chase") == "取消追價",
    }
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    cases = checks()
    payload = {"ok": all(cases.values()), "cases": cases, "safety": {
        "email_attempted": False, "line_attempted": False, "production_publish": False,
        "trading": False, "scheduler_changed": False, "main_py_executed": False,
    }}
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
