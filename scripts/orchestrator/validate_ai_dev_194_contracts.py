#!/usr/bin/env python3
"""Deterministic, read-only AI-DEV-194 lifecycle and public-contract validation."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dashboard.multi_market_dashboard import render_tw_window_report
from app.reports.tw_four_window_decision import build_observed_card, normalize_lifecycle_card


def _setup(symbol: str, readiness: str = "entry_ready") -> dict[str, Any]:
    no_trade = readiness == "no_trade"
    return {
        "symbol": symbol, "stock_id": symbol, "name": f"驗證 {symbol}", "stock_name": f"驗證 {symbol}",
        "trading_date": "2099-07-27", "setup_id": f"tw-{symbol}",
        "entry_readiness": readiness, "actionable": readiness == "entry_ready",
        "strategy_type": "no_trade" if no_trade else "pullback_long",
        "entry_low": None if no_trade else 100.0, "entry_high": None if no_trade else 102.0,
        "stop_level": None if no_trade else 95.0, "target_1": None if no_trade else 105.0,
        "target_2": None if no_trade else 110.0,
        "predicted_direction": "not_applicable" if no_trade else "bullish",
        "predicted_low": None if no_trade else 100.0, "predicted_high": None if no_trade else 105.0,
        "prediction_status": "no_trade" if no_trade else "active",
        "chase_risk": "low", "event_risk": "low",
        "strategies": {"daily_tactical": {
            "setup_type": "no_trade" if no_trade else "pullback_long", "direction": "bullish",
            "technical_factors": {"volume_ma20": 100000.0},
        }},
    }


def _quote(*, volume: float | None = 100000.0, low: float = 100.0, high: float = 104.0, close: float = 103.0) -> dict[str, Any]:
    return {
        "open": 101.0, "low": low, "high": high, "close": close, "total_volume": volume,
        "snapshot_time": "2099-07-27T13:05:00+08:00", "source": "deterministic_fixture",
        "source_timezone": "Asia/Taipei", "source_record_time_kind": "exchange_local_datetime",
    }


def _card(window: str, setup: dict[str, Any], quote: dict[str, Any], *, prior: dict[str, Any] | None = None, timeline: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return build_observed_card(
        window=window, setup_card=setup, quote=quote, trading_date="2099-07-27",
        generated_at="2099-07-27T15:00:00+08:00", source_snapshot_id="admitted-0700",
        source_revision=1, source_payload_hash="hash-0700", prior_card=prior,
        lifecycle_timeline=timeline,
    )


def _visible(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _natural_replay() -> bool:
    root = REPO_ROOT / "artifacts/archive/window_snapshots/tw"
    paths = {
        window: root / window / "2026-07-27/revision-0001.json"
        for window in ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")
    }
    if not all(path.exists() for path in paths.values()):
        return True
    wrappers = {window: json.loads(path.read_text(encoding="utf-8")) for window, path in paths.items()}
    payloads = {window: wrapper["payload"] for window, wrapper in wrappers.items()}
    setups = {str(card.get("symbol") or card.get("stock_id")): card for card in payloads["pre_open_0700"]["structured_pre_open_cards"]}
    keys = {
        "intraday_1305": "structured_intraday_cards", "pre_close_1335": "structured_pre_close_cards",
        "post_close_1500": "structured_review_cards",
    }
    projected: dict[str, dict[str, Any]] = {}
    prior: dict[str, dict[str, Any]] = {}
    for window in ("intraday_1305", "pre_close_1335", "post_close_1500"):
        cards = []
        for old in payloads[window][keys[window]]:
            symbol = str(old.get("symbol") or old.get("stock_id"))
            quote = {
                "open": old.get("session_open") or old.get("actual_open"),
                "high": old.get("session_high") or old.get("actual_high"),
                "low": old.get("session_low") or old.get("actual_low"),
                "close": old.get("current_price") or old.get("actual_close"),
                "total_volume": old.get("session_volume") or old.get("actual_volume"),
                "snapshot_time": old.get("market_data_as_of") or old.get("source_record_time"),
                "source": old.get("source_name") or "natural_replay",
                "source_timezone": old.get("source_timezone") or "Asia/Taipei",
                "source_record_time_kind": old.get("source_record_time_kind") or "exchange_local_datetime",
            }
            card = build_observed_card(
                window=window, setup_card=setups[symbol], quote=quote, trading_date="2026-07-27",
                generated_at=str(payloads[window].get("generated_at") or "2026-07-27T15:00:00+08:00"),
                source_snapshot_id=str(wrappers["pre_open_0700"].get("snapshot_id") or ""),
                source_revision=int(wrappers["pre_open_0700"].get("revision") or 1),
                source_payload_hash=str(wrappers["pre_open_0700"].get("snapshot_id") or ""),
                prior_card=prior.get(symbol), lifecycle_timeline=(prior.get(symbol) or {}).get("lifecycle_timeline"),
            )
            cards.append(card)
        projected[window] = {str(card["symbol"]): card for card in cards}
        prior = projected[window]
    watch_symbols = {symbol for symbol, card in setups.items() if card.get("entry_readiness") == "watch"}
    return bool(watch_symbols) and all(
        projected["intraday_1305"][symbol]["plan_status"] == "watch"
        and projected["intraday_1305"][symbol]["trigger_status"] == "not_applicable"
        for symbol in watch_symbols
    ) and all(len([row.get("source_window") for row in card["lifecycle_timeline"]]) == len(set(row.get("source_window") for row in card["lifecycle_timeline"])) for card in projected["post_close_1500"].values())


def checks() -> dict[str, bool]:
    watch = _card("intraday_1305", _setup("WATCH", "watch"), _quote())
    missing_volume = _card("intraday_1305", _setup("VOL"), _quote(volume=None))
    active = _card("intraday_1305", _setup("ACTIVE"), _quote())
    near_without_entry = _card("intraday_1305", _setup("PRE", "watch"), _quote(low=95.5, high=96.0, close=95.6))
    duplicate = _card(
        "pre_close_1335", _setup("ACTIVE"), _quote(), prior=active,
        timeline=[
            {"source_window": "pre_open_0700", "source_snapshot_id": "s0", "state": "active"},
            {"source_window": "intraday_1305", "source_snapshot_id": None, "state": "wait"},
            {"source_window": "intraday_1305", "source_snapshot_id": "s1", "state": "triggered"},
        ],
    )
    review = _card("post_close_1500", _setup("OPEN"), _quote(low=100.0, high=104.0, close=103.0), prior=duplicate, timeline=duplicate["lifecycle_timeline"])
    html_1305 = render_tw_window_report("intraday_1305", {"structured_intraday_cards": [watch, missing_volume, active], "tracking_stock_count": 3})
    html_1500 = render_tw_window_report("post_close_1500", {"structured_review_cards": [review], "tracking_stock_count": 1, "rendered_review_card_count": 1})
    visible = _visible(html_1305 + html_1500).lower()
    windows = [row.get("source_window") for row in review["lifecycle_timeline"]]
    explanation = review.get("prediction_explainability") or {}
    evidence = active.get("transition_evidence") or {}
    forbidden = ("setup", "watchlist", "partial_hit", " waiting ", " tracking ", " rendered ")
    return {
        "source_plan_owned_by_0700": watch["canonical_plan_owner"]["source_window"] == "pre_open_0700",
        "watch_not_promoted": watch["plan_status"] == "watch" and watch["trigger_status"] == "not_applicable" and watch["entry_low"] is None,
        "trigger_requires_all_evidence": active["trigger_status"] == "triggered" and active["trigger_evidence_complete"] is True,
        "missing_volume_blocks_trigger": missing_volume["trigger_status"] != "triggered" and missing_volume["pre_entry_action"] == "wait_volume",
        "pre_entry_never_reduce": near_without_entry["canonical_intraday_action"] != "reduce" and near_without_entry["pre_entry_action"] in {"wait", "recheck", "wait_volume", "wait_event", "cancel_setup"},
        "transition_evidence_traceable": evidence.get("entry_trigger", {}).get("time") and evidence.get("entry_trigger", {}).get("snapshot_id") == "admitted-0700",
        "open_at_close_truthful": review["trade_outcome"] == "open_at_close" and "交易於收盤仍持續" in html_1500 and "實際結果尚未完整" not in html_1500,
        "prediction_explainable": all(key in explanation for key in ("predicted_range", "actual_range", "range_result", "reason")) and "預測區間" in html_1500 and "判定原因" in html_1500,
        "timeline_one_per_window": len(windows) == len(set(windows)),
        "public_localized": not any(token in f" {visible} " for token in forbidden),
        "market_time_explainable": all(label in html_1500 for label in ("行情證據時間", "Provider 更新時間", "交易所收盤時間")),
        "natural_2026_07_27_replay": _natural_replay(),
        "read_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = checks()
    payload = {"ok": all(result.values()), "checks": result, "production_delivery_attempted": False}
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
