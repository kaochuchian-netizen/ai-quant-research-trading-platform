"""Paired technical/final evaluation with frozen origin and explicit OOS limits."""
from app.loaders.batch_universe import digest
from app.prediction.technical_first import KEY, number
from app.research.article_evidence import aware


def evaluate(decision, outcome):
    unknown = {"status": "UNKNOWN", "technical_performance": None, "final_performance": None,
               "news_adjustment_gain": None, "out_of_sample": "UNKNOWN"}
    if not decision:
        return {**unknown, "reason": "NO_FROZEN_TECHNICAL_NEWS_SPLIT"}
    if decision.get("decision_id") != digest({k: v for k, v in decision.items() if k != "decision_id"}):
        return {**unknown, "status": "FAIL", "reason": "DECISION_HASH_MISMATCH"}
    base = decision["technical_base"]
    if base.get("base_id") != digest({k: v for k, v in base.items() if k != "base_id"}):
        return {**unknown, "status": "FAIL", "reason": "BASE_HASH_MISMATCH"}
    if base["status"] != "PASS":
        return {**unknown, "reason": "TECHNICAL_DATA_BLOCKED"}
    try:
        if str(outcome.get("symbol")) != base["symbol"] or outcome.get("market") != base["market"]:
            raise ValueError("OUTCOME_IDENTITY")
        if not base.get("session_date") or outcome.get("session_date") != base["session_date"]:
            raise ValueError("OUTCOME_SESSION")
        if not outcome.get("source_ref") or outcome.get("complete") is not True:
            raise ValueError("OUTCOME_INCOMPLETE")
        # No silent default dates or current-price fallback. The full native
        # horizon must follow the recorded forecast cutoff and be complete.
        if not aware(base["as_of"]) < aware(outcome["session_open"]) < aware(outcome["session_close"]) <= aware(outcome["observed_at"]):
            raise ValueError("OUTCOME_TIME_OR_LEAKAGE")
        high, low, close = (number(outcome.get(k)) for k in ("high", "low", "close"))
        if None in (high, low, close) or not 0 < low <= close <= high:
            raise ValueError("OUTCOME_OHLC")
    except (ValueError, TypeError, KeyError):
        return {**unknown, "reason": "OUTCOME_IDENTITY_TIME_OR_COMPLETENESS_UNVERIFIED"}
    def metrics(pred):
        rng = pred.get("range_forecast") or {}
        pl = number(pred.get("predicted_session_low", rng.get("low")))
        ph = number(pred.get("predicted_session_high", rng.get("high")))
        ref = number(base.get("reference_price"))
        direction = pred.get("direction_forecast") or pred.get("one_month_trend")
        if None in (pl, ph, ref) or not 0 < pl <= ph:
            return None
        return {"range_absolute_error": round((abs(high-ph)+abs(low-pl))/2, 6),
                "range_covered": pl <= low <= high <= ph,
                "direction_correct": close > ref if direction == "bullish" else close < ref if direction == "bearish" else None,
                "direction_horizon": "one_month_not_session_scored" if "one_month_trend" in pred else "native_session"}
    technical, final = metrics(base["prediction"]), metrics(decision["final_decision"]["prediction"])
    for row in (technical, final):
        if row and row["direction_horizon"] == "one_month_not_session_scored":
            row["direction_correct"] = None
    if technical is None or final is None:
        return {**unknown, "reason": "FORECAST_METRIC_UNAVAILABLE"}
    return {"status": "EVALUATED", "decision_id": decision["decision_id"], "base_id": base["base_id"],
            "symbol": base["symbol"], "market": base["market"], "as_of": base["as_of"],
            "outcome_digest": digest(outcome), "outcome_source": outcome["source_ref"],
            "technical_performance": technical, "final_performance": final,
            "news_adjustment_gain": round(technical["range_absolute_error"]-final["range_absolute_error"], 6),
            "news_adjusted": decision["final_decision"]["news_adjustment_applied"],
            "trade_gain": "UNKNOWN_REQUIRES_TRIGGER_PATH_AND_COSTS", "out_of_sample": "UNKNOWN",
            "reason": "PAIRED_OBSERVATION_NOT_PROOF_OF_IMPROVEMENT"}


def summarize(rows):
    rows = list(rows)
    good = [r for r in rows if r.get("status") == "EVALUATED"]
    return {"status": "RECORDED" if good else "UNKNOWN", "paired_samples": len(good),
            "unknown_or_failed_samples": len(rows)-len(good), "records": rows,
            "mean_range_error_gain": sum(r["news_adjustment_gain"] for r in good)/len(good) if good else None,
            "out_of_sample_improvement": "UNKNOWN", "weights_mutated": False}


def native_outcome(market, symbol, session_date, *, high, low, close, observed_at, source_ref, complete):
    """Use the existing governed calendar, including US early closes/holidays."""
    result = dict(market=market, symbol=str(symbol), session_date=session_date, high=high, low=low, close=close,
                  observed_at=observed_at, source_ref=source_ref, complete=complete)
    try:
        from app.evaluation.session_calendar import load_calendar, session
        record = session(load_calendar(market), market, session_date)
        result.update(session_open=record["open_at"], session_close=record["close_at"])
    except (ValueError, KeyError, TypeError, OSError):
        result["complete"] = False
    return result


def immutable_us_decision(source_plan, archive_root):
    """Read only the selected admitted origin; never substitute a runtime latest."""
    import json
    from pathlib import Path
    if not source_plan or not source_plan.get("source_path"):
        return None
    try:
        path = Path(source_plan["source_path"])
        if path.is_symlink() or not path.resolve().is_relative_to(Path(archive_root).resolve()):
            return None
        if path.stat().st_size > 50_000_000:
            return None
        wrapper = json.loads(path.read_text(encoding="utf-8"))
        if (wrapper.get("snapshot_id") != source_plan.get("source_snapshot_id")
                or wrapper.get("snapshot_id") != digest({k:v for k,v in wrapper.items() if k != "snapshot_id"})
                or wrapper.get("admitted") is not True
                or str(wrapper.get("market")).upper() != "US"
                or wrapper.get("window") != "us_pre_market_2000"
                or wrapper.get("effective_trading_date") != source_plan.get("source_effective_date")):
            return None
        cards = (wrapper.get("payload", {}).get("dashboard_ready_contract") or {}).get("cards", [])
        matches = [c for c in cards if c.get("symbol") == source_plan.get("symbol")]
        if len(matches) != 1:
            return None
        decision = matches[0].get(KEY)
        if (not decision or decision.get("technical_base", {}).get("session_date") != wrapper["effective_trading_date"]
                or decision.get("technical_base", {}).get("symbol") != source_plan["symbol"]):
            return None
        return decision
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def holdout(pairs, calibration_cutoff):
    """Caller freezes policy before cutoff; never retune on the holdout."""
    rows = []
    for decision, outcome in pairs:
        if aware(decision["technical_base"]["as_of"]) <= aware(calibration_cutoff):
            rows.append({"status": "UNKNOWN", "reason": "NOT_OUT_OF_SAMPLE"})
            continue
        rows.append(evaluate(decision, outcome))
    result = summarize(rows)
    result.update(calibration_cutoff=calibration_cutoff, policy="FROZEN_NO_RETUNING",
                  improvement_claim="UNKNOWN_NO_STATISTICAL_OR_COST_VALIDATION")
    return result
