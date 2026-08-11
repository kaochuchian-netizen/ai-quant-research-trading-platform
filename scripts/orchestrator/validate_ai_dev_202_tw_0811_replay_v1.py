#!/usr/bin/env python3
"""Read-only replay of admitted 2026-08-11 TW snapshots."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.research.tw_production_intelligence_v2 import build_prediction_snapshot, evaluate_prediction, technical_evidence, verification_health, verification_record

WINDOWS = ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")


def load(window: str) -> tuple[dict, dict]:
    path = ROOT / f"artifacts/archive/window_snapshots/tw/{window}/2026-08-11/revision-0001.json"
    wrapper = json.loads(path.read_text(encoding="utf-8"))
    return wrapper, wrapper["payload"]


def cards(payload: dict, window: str) -> list[dict]:
    key = {"pre_open_0700":"structured_pre_open_cards","intraday_1305":"structured_intraday_cards","pre_close_1335":"structured_pre_close_cards","post_close_1500":"structured_review_cards"}[window]
    return [row for row in payload.get(key) or [] if isinstance(row, dict)]


def main() -> int:
    failures = []
    snapshots = {window: load(window) for window in WINDOWS}
    if not all(wrapper.get("admitted") is True for wrapper, _ in snapshots.values()): failures.append("all_snapshots_admitted")
    setup_cards = cards(snapshots["pre_open_0700"][1], "pre_open_0700")
    review_cards = cards(snapshots["post_close_1500"][1], "post_close_1500")
    intraday_cards = cards(snapshots["intraday_1305"][1], "intraday_1305")
    setup = {str(row.get("symbol") or row.get("stock_id")): row for row in setup_cards}
    review = {str(row.get("symbol") or row.get("stock_id")): row for row in review_cards}
    intraday = {str(row.get("symbol") or row.get("stock_id")): row for row in intraday_cards}
    if set(setup) != set(review) or len(setup) != 9: failures.append("symbol_partition")
    bars = {symbol: technical_evidence(card)["history_bars"] for symbol, card in setup.items()}
    if set(bars.values()) != {19}: failures.append("observed_19_bar_root_cause")
    if not all(intraday[s].get("current_price") is not None and intraday[s].get("session_high") is not None and intraday[s].get("session_low") is not None for s in setup): failures.append("intraday_price_evidence")
    predictions, evaluations, records = {}, {}, []
    generated = snapshots["pre_open_0700"][0].get("generated_at")
    reviewed = snapshots["post_close_1500"][0].get("generated_at")
    for symbol, card in setup.items():
        prediction = build_prediction_snapshot(card, effective_date="2026-08-11", generated_at=generated)
        actual_card = review[symbol]
        evaluation = evaluate_prediction(prediction, {"open":actual_card.get("actual_open"),"high":actual_card.get("actual_high"),"low":actual_card.get("actual_low"),"close":actual_card.get("actual_close")}, reviewed_at=reviewed)
        predictions[symbol] = prediction; evaluations[symbol] = evaluation; records.append(verification_record(prediction, evaluation))
    health = verification_health(records)
    if sum(item["prediction_status"] == "evaluable" for item in predictions.values()) != 9: failures.append("nine_evaluable_predictions")
    if health["evaluated"] != 9: failures.append("nine_evaluations")
    if not all(review[s].get("trade_outcome") == "no_trade" for s in setup): failures.append("trade_outcome_preserved")
    if any(item["no_trade"] is not True for item in evaluations.values()): failures.append("no_trade_prediction_independence")
    result_counts = {name: sum(item["range_result"] == name for item in evaluations.values()) for name in ("hit","partial_hit","miss","not_applicable")}
    if sum(result_counts[name] for name in ("hit","partial_hit","miss")) != 9: failures.append("prediction_evaluation_nonempty")
    if len({(item["direction_forecast"], (item["range_forecast"] or {}).get("low"), (item["range_forecast"] or {}).get("high")) for item in predictions.values()}) < 5: failures.append("prediction_differentiation")
    result = {"validator":"validate_ai_dev_202_tw_0811_replay_v1","status":"PASS" if not failures else "FAIL","failures":failures,"immutable_history_written":False,"snapshots":{w:snapshots[w][0].get("snapshot_id") for w in WINDOWS},"observed_history_bars":bars,"intraday_price_cards":sum(intraday[s].get("current_price") is not None for s in setup),"prediction_count":len(predictions),"evaluation_count":health["evaluated"],"trade_count":0,"no_trade_count":9,"prediction_distribution":result_counts,"maturity":health["stage"],"claim":"architecture replay only; not live predictive validation"}
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if not failures else 1


if __name__ == "__main__": raise SystemExit(main())
