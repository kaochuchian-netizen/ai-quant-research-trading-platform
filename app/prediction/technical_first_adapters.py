"""Adapters retain market-native calculations and action gates."""
from copy import deepcopy
from datetime import datetime

from app.prediction.technical_first import KEY, attach, technical_base, news_adjustment, final_decision


def us_base(entry, quote, technical, market_context, window, as_of):
    from app.us_stock.live_pipeline import prediction_for_symbol, dashboard_card, rating_action
    from app.strategy.dual_strategy import build_dual_strategies
    from app.us_stock.premarket_decision import build_premarket_card
    # Normalize only the existing technical/market/volatility weights. No news
    # count, neutral news placeholder or research score enters this base.
    if technical.get("ok"):
        t = technical.get("technical_score")
        m = market_context.get("market_environment_score")
        v = 45 if technical.get("volatility_state") == "high" else 55 if technical.get("volatility_state") == "low" else 50
        total = round(((50 if t is None else t) * .28 + (50 if m is None else m) * .18 + v * .10) / .56, 2)
        rating, action, confidence, level = rating_action(total, "sufficient", "unknown")
        score = dict(total_score=total, rating=rating, action=action, confidence_score=confidence,
                     confidence_level=level, confidence_status="sufficient", weight_version="technical_only_normalized_v1")
    else:
        score = dict(total_score=None, rating="資料不足", action="保守觀望", confidence_score=None,
                     confidence_level="insufficient_data", confidence_status="insufficient_data")
    empty = {"earnings": {"event_risk_level": "unknown"}}
    prediction = prediction_for_symbol(quote, technical, window, empty)
    prediction.update(one_month_trend=technical.get("trend_1m"), three_month_trend=technical.get("trend_3m"),
                      event_risk_type="UNKNOWN", news_evidence_use={"usage": "not_consumed", "candidate_ids": [], "direction_inference": False})
    strategies = build_dual_strategies("US", score, prediction, quote, technical,
                                      market_context=market_context, research=empty, generated_at=as_of)
    card = dashboard_card(entry, quote, technical, score, prediction, [], window, empty, strategies)
    gate = build_premarket_card(card, quote, empty, [], market_context, datetime.fromisoformat(as_of))
    # Non-premarket windows must not authorize a new trade from daily bars.
    if window != "us_pre_market_2000":
        gate["eligibility"].update(actionable=False, entry_ready=False, top_opportunity=False)
        gate["eligibility"]["reason_codes"].append("NATIVE_WINDOW_PLAN_REQUIRED")
        gate["trade_plan"].update(status="watch", entry=None, stop=None, target=None)
    features = technical.get("indicators") or {}
    base = technical_base(market="US", symbol=entry["symbol"], as_of=as_of, features=features,
                          bars=(technical.get("data_quality") or {}).get("history_days"),
                          source_time=quote.get("market_data_as_of"), prediction=prediction,
                          confidence=score["confidence_score"], plan=gate["trade_plan"], eligibility=gate["eligibility"],
                          price=quote.get("last_price"), source=quote.get("market_data_source"))
    if base["status"] == "DATA_BLOCKED":
        score.update(total_score=None, confidence_score=None, confidence_status="insufficient_data",
                     action="技術資料失效，暫不交易", rating="資料不足")
        strategies["daily_tactical"].update(entry_zone=None, stop_reference=None, target_zone_1=None,
                                            data_quality="insufficient_data", prediction_status="insufficient_data")
    return base, score, prediction, strategies


def apply_us(card, decision):
    final = decision["final_decision"]
    attach(card, decision)
    card["eligibility"] = deepcopy(final["eligibility"])
    card["trade_plan"] = deepcopy(final["trade_plan"])
    card["event_risk"] = {"canonical_level": final["event_risk"], "reason_codes": [final["adjustment_reason"]]}
    card["confidence"] = final["confidence"]
    if final["mode"] == "DATA_BLOCKED":
        card["action"] = "技術資料失效，暫不交易"
        card["session_predicted_high_low"] = "技術資料失效"
        card["next_session_predicted_high_low"] = "技術資料失效"
    return card


def observe_us(card, current_decision, source_plan, archive_root):
    """Later windows observe current data without creating/replacing origin plans."""
    from app.evaluation.technical_ablation import immutable_us_decision
    card["technical_observation_v1"] = deepcopy(current_decision)
    origin = immutable_us_decision(source_plan, archive_root)
    if origin:
        attach(card, origin)
    else:
        card.pop(KEY, None)
        card["decision_origin_status"] = "UNKNOWN_IMMUTABLE_TECHNICAL_SPLIT_UNAVAILABLE"
    return card


def attach_tw(card, tactical):
    factors = tactical.get("technical_factors") or {}
    forecast = card.get("prediction_snapshot_v2") or {}
    gate_reasons = list(tactical.get("risk_reasons") or [])
    actionable = card.get("actionable") is True
    if not actionable and not gate_reasons:
        gate_reasons.append("NATIVE_TW_PLAN_NOT_ACTIONABLE")
    plan = {"status": "active" if actionable else "watch", "entry": deepcopy(card.get("entry_zone")) if actionable else None,
            "stop": card.get("stop_level") if actionable else None, "target": deepcopy(card.get("target_level")) if actionable else None,
            "observation_zone": deepcopy(card.get("entry_zone")), "reward_risk": card.get("risk_reward")}
    as_of = (card.get("data_freshness") or {}).get("report_generated_at") or card.get("generated_at") or card.get("as_of") or tactical.get("generated_at")
    base = technical_base(market="TW", symbol=card["symbol"], as_of=as_of, features=factors,
                          bars=factors.get("history_days"), source_time=factors.get("history_end") or factors.get("latest_date"),
                          prediction=forecast, confidence=forecast.get("confidence"), plan=plan,
                          eligibility={"actionable": actionable, "reason_codes": gate_reasons},
                          price=factors.get("latest_close"), source=factors.get("source"), session_date=card.get("trading_date"))
    news = card.get("news_evidence") or {}
    entry = {"symbol": card["symbol"], "name": card.get("name"), "market": "TW"}
    adjustment = news_adjustment(entry=entry, as_of=as_of, items=news.get("evidence") or [], retrieval=news.get("retrieval"))
    decision = final_decision(base, adjustment)
    attach(card, decision)
    card["event_risk"] = decision["final_decision"]["event_risk"]
    if base["status"] == "DATA_BLOCKED":
        card.pop("tw_preopen_product_intelligence_v1", None)
        card.pop("tw_human_decision_summary_v1", None)
        card.update(actionable=False, entry_readiness="unavailable", entry_zone=None, stop_level=None,
                    target_level=None, entry_low=None, entry_high=None, target_1=None, target_2=None,
                    prediction_status="unavailable", predicted_low=None, predicted_high=None,
                    predicted_direction="unavailable",
                    do_not_trade_reason="；".join(base["reason_codes"]))
        card["prediction_snapshot_v2"] = deepcopy(base["prediction"])
        from app.loaders.batch_universe import digest
        card["prediction_snapshot_v2"]["prediction_identity"] = "twpred_" + digest(base)
    elif decision["final_decision"]["news_adjustment_applied"]:
        card.update(actionable=False, entry_readiness="no_trade", entry_zone=None, stop_level=None,
                    target_level=None, entry_low=None, entry_high=None, target_1=None, target_2=None,
                    do_not_trade_reason="EVENT_RISK_HIGH")
    return card
