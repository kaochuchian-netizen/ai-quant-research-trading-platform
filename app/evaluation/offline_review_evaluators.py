"""AI-DEV-251B pure derived evaluators of caller-supplied synthetic/aggregate views.

No ingestion, persistence, source dereferencing or production adapter. Metric semantics
and weights belong exclusively to the 251A contract. See the offline adapter document.
"""
from __future__ import annotations

from datetime import datetime, time, date
import hashlib
import json
import math
from zoneinfo import ZoneInfo

from app.evaluation.prediction_regression_contract import (
    CONTRACT, aware, canonical_json, contract_errors, resolve_sessions, safety_errors,
)


def load_contract():
    contract = json.loads(CONTRACT.read_text())
    if contract_errors(contract):
        raise ValueError("canonical_contract_invalid")
    return contract


def clip(value, low=0.0, high=100.0):
    return min(high, max(low, value))


class Unavailable(ValueError):
    def __init__(self, reason, field="", status="PENDING"):
        self.reason, self.field, self.status = reason, field, status
        super().__init__(reason)


class Evidence:
    """Fail closed on ambiguous meaning, provenance, chronology or fallback."""

    def __init__(self, row, cutoff):
        self.row, self.cutoff, self.used = row, cutoff, {}
        try:
            self.predicted = aware(row["prediction_at"])
            self.closed = aware(row["outcome_closed_at"])
            self.evaluated = aware(row["evaluation_at"])
        except (KeyError, TypeError, ValueError, AttributeError):
            raise Unavailable("MISSING_TIMESTAMP") from None
        if not self.predicted < self.closed <= self.evaluated <= cutoff:
            raise Unavailable("OUTCOME_NOT_MATURE")
        self.cutoff = self.evaluated
        if row.get("fallback_reason"):
            raise Unavailable("FALLBACK_EXCLUDED")

    def get(self, name, role="signal"):
        cell = self.row.get("fields", {}).get(name)
        if not isinstance(cell, dict):
            raise Unavailable("MISSING", name)
        status = cell.get("classification")
        self.used[name] = status
        if status != "AVAILABLE":
            raise Unavailable(status if status in {"PARTIAL", "MISSING", "AMBIGUOUS"} else "INVALID_CLASSIFICATION", name)
        if cell.get("role") != role:
            raise Unavailable("HINDSIGHT_ROLE_VIOLATION", name)
        ref = cell.get("source_ref")
        if not isinstance(ref, str) or not ref or cell.get("value") is None:
            raise Unavailable("MISSING_EVIDENCE", name)
        try:
            as_of, available = aware(cell["as_of"]), aware(cell["available_at"])
        except (KeyError, TypeError, ValueError, AttributeError):
            raise Unavailable("MISSING_TIMESTAMP", name) from None
        if not as_of <= available <= self.cutoff:
            raise Unavailable("AS_OF_VIOLATION", name)
        if role == "signal" and available > self.predicted:
            raise Unavailable("FUTURE_DATA_LEAKAGE", name)
        if role in {"outcome", "regret"} and as_of < self.closed:
            raise Unavailable("OUTCOME_NOT_FINAL", name)
        return cell["value"]

    def number(self, name, role="signal", low=-math.inf, high=math.inf):
        value = self.get(name, role)
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise Unavailable("INVALID_NUMBER", name)
        return value

    def positive(self, name, role="signal"):
        value = self.number(name, role, low=0)
        if value == 0:
            raise Unavailable("NONPOSITIVE_SCALE", name)
        return value

    def expect(self, name, value, role="signal"):
        if self.get(name, role) != value:
            raise Unavailable("SEMANTIC_MISMATCH", name)


def prediction_components(e):
    e.expect("confidence_event", "direction_correct")
    e.expect("atr_method", "WILDER_14_COMPLETED_POINT_IN_TIME")
    e.expect("target_semantics", "FORECAST_TARGET")
    e.expect("outcome_horizon_sessions", e.row["horizon_sessions"], "outcome")
    atr = e.positive("atr14")
    reference = e.positive("reference_price")
    close = e.positive("close", "outcome")
    low, high = e.positive("path_low", "outcome"), e.positive("path_high", "outcome")
    lower, upper = e.positive("range_low"), e.positive("range_high")
    if not low <= close <= high or lower > upper:
        raise Unavailable("INVALID_PRICE_RANGE")
    delta = close - reference
    actual = "FLAT" if abs(delta) <= 0.1 * atr else "UP" if delta > 0 else "DOWN"
    trend = e.get("trend")
    if trend not in {"UP", "DOWN", "FLAT"}:
        raise Unavailable("AMBIGUOUS", "trend")
    hit = int(trend == actual)
    probability = e.number("confidence", low=0, high=1)
    target = e.positive("target_price")
    return {
        "trend": 100.0 * hit,
        "atr_target": 100.0 * max(0, 1 - abs(target - close) / atr),
        "range_coverage": 100.0 * int(lower <= low and high <= upper),
        "confidence_calibration": 100.0 * (1 - (probability - hit) ** 2),
    }, {"interval_width_atr": (upper - lower) / atr}


def strategy_components(e):
    # Frozen assumptions are required even for simplified aggregate fixtures.
    for field in ("entry_rule", "exit_rule", "hedge_rule", "benchmark_id", "cost_basis",
                  "fill_model", "allowed_position_universe", "currency", "assumptions_version"):
        if not isinstance(e.get(field), str) or not e.get(field):
            raise Unavailable("MISSING_ASSUMPTION", field)
    e.expect("corporate_action_basis", "POINT_IN_TIME_ADJUSTED")
    e.expect("atr_method", "WILDER_14_COMPLETED_POINT_IN_TIME")
    e.expect("matched_currency_session_exposure", True, "outcome")
    e.expect("outcome_horizon_sessions", e.row["horizon_sessions"], "outcome")
    if e.get("path_resolution", "outcome") != "INTRADAY":
        raise Unavailable("AMBIGUOUS_INTRABAR_ORDER", "path_resolution", "EXCLUDED")
    exposure = e.number("recommended_exposure", low=-1, high=1)
    best = e.number("best_permitted_exposure", "regret", -1, 1)
    e.expect("best_position_universe", e.get("allowed_position_universe"), "regret")
    opportunity = e.number("best_feasible_net_profit", "regret")
    if opportunity <= 0:
        raise Unavailable("NO_POSITIVE_OPPORTUNITY", "best_feasible_net_profit", "N/A")
    profit = e.number("hypothetical_net_profit", "outcome")
    mae = e.number("hypothetical_mae", "outcome", 0)
    budget = e.positive("risk_budget")
    atr, reference = e.positive("atr14"), e.positive("reference_price")
    required = e.get("required_timing_events")
    events = e.get("timing_events", "regret")
    if not isinstance(required, list) or not required or len(set(required)) != len(required):
        raise Unavailable("MISSING_TIMING_EVENTS")
    if not isinstance(events, dict) or set(events) != set(required):
        raise Unavailable("MISSING_TIMING_EVENTS")
    timing = []
    for key in sorted(events):
        pair = events[key]
        if not isinstance(pair, list) or len(pair) != 2 or any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in pair):
            raise Unavailable("INVALID_TIMING_EVENT")
        timing.append(100 * clip(1 - abs(pair[0] - pair[1]) / atr, 0, 1))
    if exposure == 0 and not e.get("avoided_loss_evidence", "outcome"):
        raise Unavailable("MISSING_AVOIDED_LOSS_EVIDENCE")
    net_return = e.number("hypothetical_net_return", "outcome")
    benchmark = e.number("benchmark_total_return", "outcome")
    return {
        "direction_exposure": 100 * clip(1 - abs(exposure - best) / 2, 0, 1),
        "opportunity_capture": 100 * clip(profit / opportunity, 0, 1),
        "risk_avoidance": 100 * clip(1 - mae / budget, 0, 1),
        "entry_hedge_timing": math.fsum(timing) / len(timing),
        "relative_market": clip(50 + 50 * (net_return - benchmark) / (atr / reference)),
    }, {"hindsight_labels": ["best_permitted_exposure", "best_feasible_net_profit", "timing_events"],
        "causal_claim": False}


def session_context(report_date, calendar):
    latest = resolve_sessions(report_date, calendar["sessions"], calendar["coverage_through"])
    cutoff = datetime.combine(date.fromisoformat(report_date), time(17), ZoneInfo("Asia/Taipei"))
    if not calendar.get("source_ref"):
        raise ValueError("calendar_source_missing")
    expected_hash = hashlib.sha256(canonical_json(calendar["sessions"]).encode()).hexdigest()
    if calendar.get("content_hash") != expected_hash:
        raise ValueError("calendar_hash")
    completed = {m: sorted(r["session_date"] for r in calendar["sessions"]
                            if r["market"] == m and aware(r["close_at"]) <= cutoff)
                 for m in ("TW", "US")}
    return cutoff, latest, completed


def evaluate_category(category, rows, *, market, symbol, strategy_id, horizon_sessions,
                      report_date, calendar, review_session=None, evaluated_at=None):
    """One independent stock/strategy/horizon; rejects duplicates, never fills gaps."""
    if category not in {"prediction", "strategy", "improvement"}:
        raise ValueError("unsupported_category")
    contract = load_contract()
    if review_session is None and evaluated_at is None:
        cutoff, latest, completed = session_context(report_date, calendar)
    else:
        from app.evaluation.session_calendar import evaluator_calendar
        if calendar["market"] != market:
            raise ValueError("calendar_market_mismatch")
        calendar = evaluator_calendar(calendar, review_session, evaluated_at)
        cutoff = aware(evaluated_at)
        completed = {m: sorted(r["session_date"] for r in calendar["sessions"] if r["market"] == m) for m in ("TW", "US")}
        latest = {m: values[-1] if values else None for m, values in completed.items()}
    if market not in completed or type(horizon_sessions) is not int or horizon_sessions < 1:
        raise ValueError("identity")
    if safety_errors(rows):
        raise ValueError("prohibited_input")
    fn = {"prediction": prediction_components, "strategy": strategy_components,
          "improvement": improvement_components}[category]
    selected = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("invalid_row")
        if (row.get("market"), row.get("symbol"), row.get("strategy_id"), row.get("horizon_sessions")) == (market, symbol, strategy_id, horizon_sessions):
            selected.append(row)
    by_session = {}
    for row in selected:
        by_session.setdefault(row.get("session_date"), []).append(row)
    evaluated = {}
    for session in completed[market][-10:]:
        candidates = by_session.get(session, [])
        result = {"status": "PENDING", "score": None, "components": {}, "missing_fields": [], "reasons": []}
        if len(candidates) != 1:
            result["reasons"] = ["MISSING_SESSION" if not candidates else "AMBIGUOUS_DUPLICATE_SESSION"]
            evaluated[session] = result
            continue
        row = candidates[0]
        e = None
        try:
            e = Evidence(row, cutoff)
            e.calendar = calendar
            market_calendar = sorted((r for r in calendar["sessions"] if r["market"] == market), key=lambda r: r["session_date"])
            calendar_row = next(r for r in market_calendar if r["session_date"] == session)
            first_index = market_calendar.index(calendar_row) - horizon_sessions + 1
            if first_index < 0:
                raise Unavailable("HORIZON_CALENDAR_INSUFFICIENT")
            if e.closed != aware(calendar_row["close_at"]):
                raise Unavailable("SESSION_CLOSE_MISMATCH")
            if e.predicted >= aware(market_calendar[first_index]["open_at"]):
                raise Unavailable("PREDICTION_NOT_BEFORE_SESSION")
            if not isinstance(row.get("fields"), dict):
                raise Unavailable("INVALID_FIELDS")
            # Every signal supplied must satisfy as-of even if not used by this metric.
            for name, cell in sorted(row.get("fields", {}).items()):
                if not isinstance(cell, dict):
                    raise Unavailable("INVALID_FIELD", name)
                if cell.get("role") not in {"signal", "outcome", "regret"}:
                    raise Unavailable("HINDSIGHT_ROLE_VIOLATION", name)
                if cell.get("role") == "signal" and cell.get("classification") == "AVAILABLE":
                    e.get(name)
            components, diagnostics = fn(e)
            result.update(status="ELIGIBLE", components=components, diagnostics=diagnostics,
                          score=math.fsum(components[k] * w / 100 for k, w in contract["weights_percent"][category].items()))
        except Unavailable as error:
            result.update(status=error.status, reasons=[error.reason], missing_fields=[error.field] if error.field else [])
        result["source_coverage"] = dict(sorted(e.used.items())) if e else {}
        result["source_references"] = {name: cell.get("source_ref") for name, cell in sorted(row.get("fields", {}).items())
                                       if isinstance(cell, dict) and e and name in e.used} if isinstance(row.get("fields"), dict) else {}
        result["missing_fields"] = sorted(set(result["missing_fields"] + [name for name, cell in row.get("fields", {}).items()
                                                if isinstance(cell, dict) and cell.get("classification") != "AVAILABLE"])) if isinstance(row.get("fields"), dict) else result["missing_fields"]
        evaluated[session] = result
    windows = {}
    for n in (3, 10):
        dates = completed[market][-n:]
        eligible = [evaluated[d]["score"] for d in dates if evaluated[d]["status"] == "ELIGIBLE"]
        ok = len(dates) == len(eligible) == n
        windows[str(n)] = {"sessions": dates, "sample_size": len(eligible), "expected": n,
                           "status": "ELIGIBLE" if ok else "INSUFFICIENT_SAMPLE",
                           "score": math.fsum(eligible) / n if ok else None}
    ready = all(w["status"] == "ELIGIBLE" for w in windows.values())
    score = (windows["3"]["score"] * contract["weights_percent"]["time"]["last_3_sessions"] / 100
             + windows["10"]["score"] * contract["weights_percent"]["time"]["last_10_sessions"] / 100) if ready else None
    component_means = {}
    if ready:
        for component in contract["weights_percent"][category]:
            component_means[component] = math.fsum(
                math.fsum(evaluated[d]["components"][component] for d in windows[str(n)]["sessions"]) / n * weight / 100
                for n, weight in ((3, contract["weights_percent"]["time"]["last_3_sessions"]),
                                  (10, contract["weights_percent"]["time"]["last_10_sessions"])))
    result = {"status": "ELIGIBLE" if ready else "INSUFFICIENT_SAMPLE", "score": score,
            "latest_session": latest[market], "windows": windows, "evidence": evaluated,
            "component_scores": component_means,
            "confidence": "DESCRIPTIVE_ONLY" if ready else "INSUFFICIENT",
            "evidence_grade": "SYNTHETIC_OR_CALLER_ATTESTED", "production_ready": False}
    if category == "improvement":
        result["unique_fix_count"] = len({r["diagnostics"]["fix_id"] for r in evaluated.values() if r["status"] == "ELIGIBLE"})
        result["effect_summary"] = effect_summary(component_means)
        if not ready:
            result["status"] = "N/A" if evaluated and all(r["status"] == "N/A" for r in evaluated.values()) else "PENDING"
        elif result["effect_summary"]["realized_prediction_effect"] == "NEUTRAL" and score > 50:
            result["status"] = "DIAGNOSIS_POSITIVE_EFFECT_NEUTRAL"
        else:
            result["status"] = "POSITIVE" if score > 50 else "NO_NET_EVIDENCE" if score == 50 else "NEGATIVE"
    return result


def evaluate_prediction(rows, **context):
    return evaluate_category("prediction", rows, **context)


def evaluate_strategy(rows, **context):
    return evaluate_category("strategy", rows, **context)


def evaluate_improvement(rows, **context):
    return evaluate_category("improvement", rows, **context)


def improvement_effect(baseline, post_fix, *, expected_sessions, matched_identity,
                       effective_at, cutoff):
    """Canonical D+3/D+10 delta only; 50 is neutral for this effect subscore.

    Cohorts are sanitized per-session eligible prediction metric aggregates, not
    editable predictions. Identity includes market/symbol/strategy/horizon/regime.
    A frozen baseline is required; later evidence is exclusively outcome evidence.
    """
    n = len(expected_sessions)
    if n not in (3, 10) or len(set(expected_sessions)) != n:
        raise ValueError("effect_window")
    if safety_errors([baseline, post_fix]):
        raise ValueError("prohibited_input")
    try:
        effective, limit = aware(effective_at), aware(cutoff)
        if len(baseline) != n or len(post_fix) != n:
            raise Unavailable("INSUFFICIENT_SAMPLE", status="INSUFFICIENT_SAMPLE")
        if sorted(r.get("session_date", "") for r in post_fix) != sorted(expected_sessions):
            raise Unavailable("POST_FIX_SESSION_MISMATCH")
        if len({r.get("session_date") for r in baseline}) != n:
            raise Unavailable("DUPLICATE_BASELINE")
        for cohort, rows in (("baseline", baseline), ("post_fix", post_fix)):
            for row in rows:
                if row.get("matched_identity") != matched_identity:
                    raise Unavailable("UNMATCHED_COHORT")
                if row.get("classification") != "AVAILABLE" or row.get("status") != "ELIGIBLE":
                    raise Unavailable("INELIGIBLE_COHORT")
                score = row.get("score")
                if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 100:
                    raise Unavailable("INVALID_COHORT_SCORE")
                if not row.get("source_ref") or not row.get("metric_spec_version"):
                    raise Unavailable("MISSING_COHORT_PROVENANCE")
                closed, available = aware(row["closed_at"]), aware(row["available_at"])
                if closed > available or available > limit:
                    raise Unavailable("COHORT_AS_OF_VIOLATION")
                if cohort == "baseline" and not closed <= available <= aware(row["frozen_at"]) <= effective:
                    raise Unavailable("BASELINE_NOT_FROZEN")
                if cohort == "post_fix" and closed <= effective:
                    raise Unavailable("POST_FIX_BEFORE_EFFECTIVE")
        if len({r["metric_spec_version"] for r in baseline + post_fix}) != 1:
            raise Unavailable("METRIC_VERSION_MISMATCH")
        delta = math.fsum(r["score"] for r in post_fix) / n - math.fsum(r["score"] for r in baseline) / n
        return {"status": "ELIGIBLE", "score": clip(50 + delta), "delta": delta,
                "baseline_count": n, "post_fix_count": n, "causal_claim": False,
                "interpretation": "UNCHANGED" if delta == 0 else "IMPROVED" if delta > 0 else "REGRESSED"}
    except Unavailable as error:
        return {"status": error.status, "score": None, "reasons": [error.reason], "causal_claim": False}
    except (KeyError, TypeError, ValueError, AttributeError):
        return {"status": "PENDING", "score": None, "reasons": ["INVALID_COHORT_METADATA"], "causal_claim": False}


def improvement_components(e):
    fix = e.get("fix", "outcome")
    if not isinstance(fix, dict) or fix.get("status") != "IMPLEMENTED":
        raise Unavailable("NO_IMPLEMENTED_FIX")
    finding = e.get("finding", "outcome")
    identity = {k: e.row[k] for k in ("market", "symbol", "strategy_id", "horizon_sessions")}
    identity["regime"] = fix.get("regime")
    try:
        effective = aware(fix["effective_at"])
        if not identity["regime"] or not fix["source_ref"] or not fix["fix_id"]:
            raise Unavailable("MISSING_FIX_PROVENANCE")
        if not aware(fix["approved_at"]) <= effective < e.closed:
            raise Unavailable("FIX_NOT_EFFECTIVE")
        if not (finding["status"] == "CONFIRMED" and finding["finding_id"] == fix["finding_id"]
                and finding["immutable_error_ref"] and aware(finding["confirmed_at"]) <= effective):
            raise Unavailable("FINDING_NOT_CONFIRMED")
        market_calendar = sorted((r for r in e.calendar["sessions"] if r["market"] == e.row["market"]), key=lambda r: r["session_date"])
        effective_session = next((r for r in market_calendar if r["session_date"] == fix["effective_session"]), None)
        if effective_session is None or not aware(effective_session["open_at"]) <= effective <= aware(effective_session["close_at"]):
            raise Unavailable("FIX_EFFECTIVE_SESSION_MISMATCH")
        post_calendar = [r for r in market_calendar if r["session_date"] > fix["effective_session"]][:10]
        if len(post_calendar) != 10 or aware(post_calendar[-1]["close_at"]) > e.closed:
            raise Unavailable("IMMATURE_D10")
        post = e.get("post_fix_cohort", "outcome")
        if not isinstance(post, list) or len(post) != 10:
            raise Unavailable("INSUFFICIENT_SAMPLE")
        expected = [r["session_date"] for r in post_calendar]
        if sorted(r["session_date"] for r in post) != expected:
            raise Unavailable("POST_FIX_SESSION_MISMATCH")
        calendar_by_date = {r["session_date"]: r for r in market_calendar}
        components = {"finding_confirmed": 100.0}
        for n in (3, 10):
            baseline = e.get(f"baseline_{n}", "outcome")
            if not isinstance(baseline, list):
                raise Unavailable("MISSING_BASELINE")
            for row in baseline + post:
                session = calendar_by_date.get(row["session_date"])
                if session is None or aware(row["closed_at"]) != aware(session["close_at"]):
                    raise Unavailable("COHORT_SESSION_CLOSE_MISMATCH")
            effect = improvement_effect(baseline, sorted(post, key=lambda r: r["session_date"])[:n],
                                        expected_sessions=expected[:n], matched_identity=identity,
                                        effective_at=fix["effective_at"], cutoff=e.cutoff.isoformat())
            if effect["score"] is None:
                raise Unavailable(effect["reasons"][0])
            components[f"d{n}_effect"] = effect["score"]
        recurrence = e.get("recurrence", "outcome")
        if not isinstance(recurrence, list) or sorted(r["session_date"] for r in recurrence) != expected:
            raise Unavailable("RECURRENCE_WINDOW_INCOMPLETE")
        if not fix["detector_version"] or aware(fix["detector_frozen_at"]) > effective:
            raise Unavailable("DETECTOR_NOT_FROZEN")
        count, opportunities = 0, 0
        for row in recurrence:
            if (row["detector_version"] != fix["detector_version"] or not row["source_ref"]
                    or row["classification"] != "AVAILABLE"
                    or not aware(calendar_by_date[row["session_date"]]["close_at"]) <= aware(row["available_at"]) <= e.cutoff):
                raise Unavailable("RECURRENCE_EVIDENCE_INVALID")
            observed, recurring = row["observable_opportunities"], row["recurrence_count"]
            if type(observed) is not int or type(recurring) is not int or not 0 <= recurring <= observed:
                raise Unavailable("RECURRENCE_COUNTS_INVALID")
            opportunities += observed
            count += recurring
        if opportunities == 0:
            raise Unavailable("NO_OBSERVABLE_OPPORTUNITIES", status="N/A")
        components["non_recurrence"] = 100 * (1 - count / opportunities)
        return components, {"fix_id": fix["fix_id"], "cohort_sizes": {"d3": 3, "d10": 10},
                            "observable_opportunities": opportunities, "recurrence_count": count,
                            "causal_claim": False, "effect_summary": effect_summary(components)}
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        if isinstance(error, Unavailable):
            raise
        raise Unavailable("INVALID_IMPROVEMENT_METADATA") from None


def effect_summary(components):
    if not components:
        return {"diagnosis_effect": "PENDING", "realized_prediction_effect": "PENDING", "recurrence_effect": "PENDING"}
    d3, d10 = components["d3_effect"], components["d10_effect"]
    realized = ("NEUTRAL" if d3 == d10 == 50 else "IMPROVED" if d3 >= 50 and d10 >= 50
                else "REGRESSED" if d3 <= 50 and d10 <= 50 else "MIXED")
    return {"diagnosis_effect": "CONFIRMED" if components["finding_confirmed"] == 100 else "UNCONFIRMED",
            "realized_prediction_effect": realized,
            "recurrence_effect": "NO_RECURRENCE_OBSERVED" if components["non_recurrence"] == 100 else "RECURRENCE_OBSERVED"}


def evaluate_stock(rows, **context):
    """Presentation projection, not a stored daily_scorecard or report manifest."""
    results = {"prediction": evaluate_prediction(rows, **context),
               "improvement": evaluate_improvement(rows, **context),
               "strategy": evaluate_strategy(rows, **context)}
    explanation = {
        "prediction": "依已完成交易日的方向、目標價、區間與校準證據評估；僅為離線描述性結果。",
        "strategy": "依凍結假設評估假想策略；後見結果只供檢討，不是當時可用訊號。",
    }
    effect = results["improvement"]["effect_summary"]["realized_prediction_effect"]
    explanation["improvement"] = {
        "NEUTRAL": "改善分數衡量回歸驗證與閉環品質；D+3／D+10 預測效果持平，不能宣稱預測準確度已提升。",
        "IMPROVED": "閉環有正向證據，匹配樣本的預測效果改善；尚不能主張因果效果。",
        "REGRESSED": "匹配樣本的預測效果退步；閉環總分不可替代效果判讀。",
        "MIXED": "D+3／D+10 預測效果不一致，尚不能宣稱持續改善。",
        "PENDING": "改善閉環證據不足，分數待定；不以零分替代。",
    }[effect]
    names = {"prediction": "prediction_accuracy_score", "improvement": "improvement_accuracy_score", "strategy": "investment_strategy_score"}
    user = {names[k]: {"score": v["score"], "status": v["status"],
                      "explanation": explanation[k] if v["score"] is not None or k == "improvement" else "必要樣本或欄位不足，暫不給分。"}
            for k, v in results.items()}
    user["improvement_accuracy_score"]["effect_summary"] = results["improvement"]["effect_summary"]
    for category, name in (("prediction", "next_prediction_improvements"), ("improvement", "next_improvement_loop_actions"), ("strategy", "next_strategy_actions")):
        reasons = sorted({reason for row in results[category]["evidence"].values() for reason in row["reasons"]})
        user[name] = ["補齊並確認證據：" + reason for reason in reasons] or ["保留證據並於下一個已完成交易日檢討；不自動變更模型或策略。"]
    weights = load_contract()["weights_percent"]["composite"]
    composite = math.fsum(results[k]["score"] * w / 100 for k, w in weights.items()) if all(v["score"] is not None for v in results.values()) else None
    return {"market": context["market"], "symbol": context["symbol"], "user_facing": user,
            "internal_evidence": {"evaluators": results,
                "source_coverage": {k: {d: r.get("source_coverage", {}) for d, r in v["evidence"].items()} for k, v in results.items()},
                "missing_fields": sorted({f for v in results.values() for r in v["evidence"].values() for f in r["missing_fields"]}),
                "sample_size": {k: {n: w["sample_size"] for n, w in v["windows"].items()} for k, v in results.items()},
                "confidence": "DESCRIPTIVE_ONLY" if all(v["score"] is not None for v in results.values()) else "INSUFFICIENT",
                "evidence_grade": "SYNTHETIC_OR_CALLER_ATTESTED",
                "predecessor_report_reference": {"report_id": None, "content_hash": None, "status": "PENDING_251C"},
                "composite": {"score": composite, "status": "ELIGIBLE" if composite is not None else "PENDING"},
                "production_ready": False}}
