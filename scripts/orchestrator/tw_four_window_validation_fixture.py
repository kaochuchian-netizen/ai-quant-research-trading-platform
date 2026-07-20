"""Deterministic no-send fixture for AI-DEV-186 validators."""
from __future__ import annotations

from app.reports.tw_four_window_decision import aggregate_cards, build_observed_card, stable_hash
from app.reports.tw_pre_open_structured import aggregate as aggregate_pre_open, build_card

SYMBOLS = ["2330", "2337", "2353", "6873", "4743", "2305", "00878", "1409", "009816"]
TRADING_DATE = "2099-07-20"


def _tactical(index: int) -> dict:
    no_trade = index == 4
    return {
        "stock_id": SYMBOLS[index], "stock_name": f"驗證標的 {index + 1}",
        "setup_type": "no_trade" if no_trade else "pullback_long",
        "direction": "neutral" if no_trade else "bullish",
        "action": "暫不操作" if no_trade else "觀察切入",
        "entry_zone": None if no_trade else {"low": 100.0 + index, "high": 102.0 + index},
        "stop_invalidation": None if no_trade else {"price": 95.0 + index, "reason": "跌破失效"},
        "target_1": None if no_trade else {"low": 105.0 + index, "high": 107.0 + index},
        "target_2": None if no_trade else {"low": 111.0 + index, "high": 113.0 + index},
        "reward_risk": None if no_trade else 1.6,
        "chase_risk": "high" if index == 7 else "normal", "event_risk": "low",
        "data_quality": "partial" if index == 6 else "complete",
        "reasons": ["趨勢與風險報酬符合門檻"], "risk_reasons": ["避免追價"] if index == 7 else [],
        "playbook": {"entry_condition": "價格進入區間且量能確認"},
        "technical_factors": {"volume_ma20": 100000.0},
    }


def payloads() -> dict[str, dict]:
    pre_cards = []
    for index, symbol in enumerate(SYMBOLS):
        pre_cards.append(build_card(
            symbol=symbol, name=f"驗證標的 {index + 1}", trading_date=TRADING_DATE,
            indicator={"date": "2099-07-19", "close": 100 + index, "trend": "sideways"},
            adr={"status": "normal", "change_rate": -0.5},
            news={"error": "504 DEADLINE_EXCEEDED"} if index == 0 else [{"summary": "無新增重大事件"}],
            chip={"status": "normal"}, score={"total_score": 80 - index, "rating": "A", "action": "wait"},
            analysis={"raw": ["2330", "2337"]}, tactical=_tactical(index),
            missing_fields=["news"] if index == 0 else [], generated_at="2099-07-20T07:05:00+08:00",
        ))
    pre_summary = aggregate_pre_open(pre_cards, SYMBOLS)
    pre = {
        "schema_version": "tw_window_snapshot_payload_v1", "runtime_provenance": "scheduled_production",
        "market": "TW", "window": "pre_open_0700", "effective_trading_date": TRADING_DATE,
        "generated_at": "2099-07-20T07:05:00+08:00", "tracking_stock_count": 9,
        "tracking_symbols": SYMBOLS, "structured_card_count": 9, "rendered_card_count": 9,
        "structured_pre_open_cards": pre_cards, "cards": pre_cards, "pre_open_summary": pre_summary,
    }
    parent_hash = stable_hash(pre)
    windows = {"pre_open_0700": pre}
    for window, timestamp in (("intraday_1305", "13:04:30"), ("pre_close_1335", "13:34:30"), ("post_close_1500", "13:30:00")):
        cards = []
        for index, setup in enumerate(pre_cards):
            entry = 100.0 + index
            quote = {
                "stock_id": SYMBOLS[index], "open": entry + 1, "low": entry,
                "high": entry + (8 if index == 0 else 14 if index == 1 else 1),
                "close": entry + 2, "total_volume": 100000 + index * 10000,
                "snapshot_time": f"{TRADING_DATE} {timestamp}", "source": "deterministic_observed_fixture",
            }
            if index == 2:
                quote.update({"low": entry - 6, "close": entry - 4})
            if index == 3:
                quote.update({"low": entry + 3, "high": entry + 4, "close": entry + 3})
            if index == 5 and window == "post_close_1500":
                quote = {}
            card = build_observed_card(
                window=window, setup_card=setup, quote=quote, trading_date=TRADING_DATE,
                generated_at=f"{TRADING_DATE}T{timestamp}+08:00", source_snapshot_id="fixture-preopen-snapshot",
                source_revision=1, source_payload_hash=parent_hash,
            )
            cards.append(card)
        summary = aggregate_cards(window, cards)
        key = {"intraday_1305": "structured_intraday_cards", "pre_close_1335": "structured_pre_close_cards", "post_close_1500": "structured_review_cards"}[window]
        windows[window] = {
            "schema_version": "tw_window_snapshot_payload_v1", "runtime_provenance": "scheduled_production",
            "market": "TW", "window": window, "effective_trading_date": TRADING_DATE,
            "generated_at": f"{TRADING_DATE}T{timestamp}+08:00", "source_data_time": f"{TRADING_DATE} {timestamp}",
            "tracking_stock_count": 9, "tracking_symbols": SYMBOLS, "structured_card_count": 9,
            key: cards, "cards": cards, "tw_window_summary": summary,
        }
    return windows
