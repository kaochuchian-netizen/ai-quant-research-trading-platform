#!/usr/bin/env python3
"""Deterministic, read-only AI-DEV-191 lifecycle validation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard.multi_market_dashboard import render_tw_window_report
from app.reports.tw_1335_snapshot_delivery import render_line as render_1335_line
from app.reports.tw_four_window_decision import (
    aggregate_cards,
    build_observed_card,
    normalize_lifecycle_card,
    render_intraday_email,
    render_intraday_line,
)
from app.reports.tw_post_close_review import render_email as render_1500_email, render_line as render_1500_line


def _setup(symbol: str = "TEST", *, plan: str = "active") -> dict[str, Any]:
    no_trade = plan == "no_trade"
    return {
        "symbol": symbol, "stock_id": symbol, "name": f"驗證 {symbol}", "stock_name": f"驗證 {symbol}",
        "trading_date": "2099-07-23", "setup_id": f"setup-{symbol}",
        "entry_readiness": "no_trade" if no_trade else "entry_ready" if plan == "active" else "watch",
        "strategy_type": "no_trade" if no_trade else "pullback_long",
        "entry_low": None if no_trade else 100.0, "entry_high": None if no_trade else 102.0,
        "stop_level": None if no_trade else 95.0, "target_1": None if no_trade else 105.0,
        "target_2": None if no_trade else 110.0, "predicted_direction": "not_applicable" if no_trade else "bullish",
        "predicted_low": None if no_trade else 100.0, "predicted_high": None if no_trade else 105.0,
        "prediction_status": "no_trade" if no_trade else "active",
        "action": "暫不操作" if no_trade else "觀察切入", "actionable": plan == "active",
        "strategies": {"daily_tactical": {
            "setup_type": "no_trade" if no_trade else "pullback_long",
            "technical_factors": {"volume_ma20": 100000.0},
        }},
    }


def _quote(*, low: float, high: float, close: float, volume: float = 90000.0) -> dict[str, Any]:
    return {
        "open": 101.0, "low": low, "high": high, "close": close, "total_volume": volume,
        "snapshot_time": "2099-07-23T13:05:00+08:00", "source": "deterministic_fixture",
        "source_timezone": "Asia/Taipei", "source_record_time_kind": "exchange_local_datetime",
    }


def _card(window: str, setup: dict[str, Any], quote: dict[str, Any], prior: dict[str, Any] | None = None) -> dict[str, Any]:
    return build_observed_card(
        window=window, setup_card=setup, quote=quote, trading_date="2099-07-23",
        generated_at="2099-07-23T15:00:00+08:00", source_snapshot_id="preopen-snapshot",
        source_revision=1, source_payload_hash="preopen-hash", prior_card=prior,
    )


def checks() -> dict[str, bool]:
    no_trade = _card("intraday_1305", _setup("NO", plan="no_trade"), _quote(low=98, high=104, close=101))
    invalidated = _card("intraday_1305", _setup("LOSS"), _quote(low=94, high=102, close=96))
    wait_volume = _card("intraday_1305", _setup("WAIT"), _quote(low=100, high=103, close=101, volume=30000))
    both = _card("pre_close_1335", {
        **_setup("BOTH"), "stop_level": 99.0, "target_1": 101.0,
    }, _quote(low=99.5, high=101.2, close=100.0), wait_volume)
    open_close = _card("post_close_1500", _setup("OPEN"), _quote(low=99, high=104, close=103), both)
    win = _card("post_close_1500", _setup("WIN"), _quote(low=99, high=106, close=105), both)
    loss = _card("post_close_1500", _setup("LOSS"), _quote(low=94, high=102, close=96), invalidated)
    no_trade_close = _card("post_close_1500", _setup("NO", plan="no_trade"), _quote(low=98, high=104, close=101), no_trade)
    preclose_cards = [
        normalize_lifecycle_card({**both, "symbol": "H", "overnight_action": "hold"}, "pre_close_1335"),
        normalize_lifecycle_card({**both, "symbol": "HP", "overnight_action": "hold_with_protection"}, "pre_close_1335"),
        normalize_lifecycle_card({**both, "symbol": "W", "overnight_action": "watch"}, "pre_close_1335"),
        normalize_lifecycle_card({**both, "symbol": "R", "overnight_action": "reduce"}, "pre_close_1335"),
        normalize_lifecycle_card({**invalidated, "symbol": "E", "window": "pre_close_1335"}, "pre_close_1335"),
        normalize_lifecycle_card({**no_trade, "symbol": "N", "window": "pre_close_1335"}, "pre_close_1335"),
    ]
    preclose_summary = aggregate_cards("pre_close_1335", preclose_cards)
    review_cards = [win, loss, open_close, no_trade_close]
    review_summary = aggregate_cards("post_close_1500", review_cards)
    payload_1305 = {"structured_intraday_cards": [no_trade, invalidated, wait_volume], "source_data_time": "2099-07-23T13:05:00+08:00"}
    payload_1500 = {"structured_review_cards": review_cards, "tracking_stock_count": len(review_cards), "rendered_review_card_count": len(review_cards)}
    html_1305 = render_tw_window_report("intraday_1305", payload_1305)
    html_1500 = render_tw_window_report("post_close_1500", payload_1500)
    email_1305 = render_intraday_email(payload_1305, "https://example.invalid/tw/1305")
    line_1305 = render_intraday_line(payload_1305, "https://example.invalid/tw/1305")
    email_1500 = render_1500_email(payload_1500, "https://example.invalid/tw/1500")
    line_1500 = render_1500_line(payload_1500, "https://example.invalid/tw/1500")
    forbidden = ("stop_invalidated", "reduce_risk", "wait_volume", ">no_trade<", ">triggered<", ">invalidated<")
    return {
        "no_trade_trigger_not_applicable": no_trade["trigger_status"] == "not_applicable" and no_trade["evidence_status"] == "not_applicable",
        "no_trade_distances_hidden": all(no_trade[key] is None for key in ("distance_to_stop_pct", "distance_to_target_1_pct")),
        "invalidated_to_exit": invalidated["trigger_status"] == "invalidated" and invalidated["canonical_intraday_action"] == "exit" and normalize_lifecycle_card(invalidated, "pre_close_1335")["overnight_action"] == "exit",
        "wait_volume_canonical": wait_volume["canonical_intraday_action"] == "wait_volume",
        "both_near": both["risk_state"] == "both_near",
        "volume_contract": wait_volume["lookback_sessions"] == 20 and "prorated" in wait_volume["volume_ratio_basis"],
        "proximity_contract": wait_volume["target_near_threshold_pct"] == wait_volume["stop_near_threshold_pct"] == 1.5,
        "overnight_partition": sum(preclose_summary["overnight_action_counts"].values()) == len(preclose_cards) == 6,
        "reduce_exit_exclusive": preclose_summary["overnight_action_symbols"]["reduce"] == ["R"] and preclose_summary["overnight_action_symbols"]["exit"] == ["E"],
        "open_at_close": open_close["trade_outcome"] == "open_at_close" and open_close["evidence_status"] == "complete",
        "win_loss": win["trade_outcome"] == "win" and loss["trade_outcome"] == "loss",
        "no_trade_outcome": no_trade_close["trade_outcome"] == "no_trade" and no_trade_close["mfe"]["status"] == "not_applicable",
        "prediction_trade_separate": win["prediction_evaluation"]["range_result"] in {"hit", "partial_hit", "miss"} and win["trade_outcome"] == "win",
        "mfe_mae_contract": all(key in win["mfe"] for key in ("pct", "unit", "reference_price", "reference_type", "resolution")) and win["mfe"]["unit"] == "pct",
        "timeline_identity": len(open_close["lifecycle_timeline"]) >= 3 and all("source_window" in row and "effective_date" in row for row in open_close["lifecycle_timeline"]),
        "trade_aggregate": review_summary["trade_outcome_counts"]["win"] == 1 and review_summary["trade_outcome_counts"]["loss"] == 1 and review_summary["trade_outcome_counts"]["open_at_close"] == 1 and review_summary["trade_outcome_counts"]["no_trade"] == 1,
        "public_enum_localized": not any(token in html_1305 for token in forbidden),
        "compact_no_trade": "compact-no-trade-card" in html_1305 and "False Breakout" not in html_1500,
        "notification_parity": "策略失效 1" in email_1305 and "策略失效 1" in line_1305 and "收盤未結束 1" in email_1500 and "收盤未結束 1" in line_1500,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = checks()
    payload = {"ok": all(result.values()), "checks": result, "read_only": True, "production_delivery_attempted": False}
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
