"""252 pure capability-aware evidence contracts; no fetching, clock or actions."""
from copy import deepcopy
import math
from app.evaluation.offline_report_projection import digest
from app.evaluation.prediction_regression_contract import aware, stamp
from app.evaluation.offline_review_evaluators import realized_prediction_direction
from app.evaluation.session_calendar import session, validate_calendar, ZONES

VERSION = "production_evidence_accumulation_v1"
EVENT = "prediction_direction_event_v1"
LEGACY_EVENT = "SESSION_OPEN_TO_CLOSE_REVIEW"
MAPPING = {"TW": {"pre_open_0700": 0, "intraday_1305": 1, "pre_close_1335": 1, "post_close_1500": 1},
           "US": {"us_pre_market_2000": 0, "us_intraday_2300": 1, "us_post_close_review_0630": 1}}
STATES = {"HISTORICAL_INELIGIBLE", "WAITING_OUTCOME", "INSUFFICIENT_SAMPLE",
          "READY_FOR_EVALUATION", "EVALUATED", "BLOCKED_INPUT"}

def verify(value):
    if not isinstance(value, dict) or value.get("content_hash") != digest({k:v for k,v in value.items() if k != "content_hash"}):
        raise ValueError("EVIDENCE_DIGEST")
    return value

def positive(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError("INVALID_PRICE")
    return value

def capability(market, stream):
    if stream not in MAPPING.get(market, {}):
        raise ValueError("UNKNOWN_STREAM")
    return "CAPABILITY_UNAVAILABLE" if market == "US" else "NATIVE_DIRECTION" if stream == "pre_open_0700" else "INHERITED_REFERENCE_ONLY"

def horizon(calendar, market, stream, day, *, native=False):
    """Mapping is dormant unless a genuine native producer activates it."""
    if not native:
        raise ValueError("NO_NATIVE_PREDICTION")
    current = session(calendar, market, day)
    offset = MAPPING[market][stream]
    if offset:
        current = next((r for r in calendar["days"] if r["session_date"] > day and r["state"] in {"NORMAL", "EARLY_CLOSE"}), None)
        if current is None:
            raise ValueError("CALENDAR_OUTSIDE_COVERAGE")
    return {"market": market, "session_date": current["session_date"], "open_at": current["open_at"],
            "close_at": current["close_at"], "horizon_sessions": 1, "calendar_hash": calendar["content_hash"]}

def feature(name, value, *, source, revision, source_digest, as_of, available_at, producer):
    positive(value)
    if not source or not revision or not producer or len(source_digest) != 64 or aware(as_of) > aware(available_at):
        raise ValueError("FEATURE_PROVENANCE")
    return stamp({"identity": name, "value": value, "source": source, "source_revision": revision,
                  "source_digest": source_digest, "as_of": as_of, "available_at": available_at, "producer": producer})

def freeze(*, prediction_id, symbol, direction, frozen_at, reference, atr, calendar, review_session,
           producer, event_confidence=None, market="TW", stream="pre_open_0700", prediction_features=None):
    if (market, stream) not in {("TW","pre_open_0700"),("US","us_pre_market_2000")}:
        raise ValueError("NATIVE_STREAM")
    h = horizon(calendar, market, stream, review_session, native=True)
    if aware(frozen_at) >= aware(h["open_at"]):
        raise ValueError("PREDICTION_NOT_BEFORE_SESSION")
    for f in (reference, atr, *(prediction_features or {}).values()):
        verify(f); positive(f["value"])
        if not aware(f["as_of"]) <= aware(f["available_at"]) <= aware(frozen_at):
            raise ValueError("FUTURE_FEATURE")
    if atr["producer"] != "WILDER_14_COMPLETED_POINT_IN_TIME":
        raise ValueError("ATR_METHOD")
    if direction not in {"UP", "DOWN", "FLAT"} or not prediction_id or not producer or not symbol:
        raise ValueError("PREDICTION_IDENTITY")
    event = {"version": EVENT, "reference_digest": reference["content_hash"], "atr_digest": atr["content_hash"],
             "flat_band_rule": "251A.prediction.trend", "horizon": h}
    if event_confidence is not None:
        verify(event_confidence)
        if (event_confidence.get("prediction_id") != prediction_id or event_confidence.get("event") != event
            or event_confidence.get("frozen_at") != frozen_at or not event_confidence.get("producer")
            or type(event_confidence.get("value")) not in (int, float) or not 0 <= event_confidence["value"] <= 1):
            raise ValueError("EVENT_CONFIDENCE_IDENTITY")
    result = {"schema_version": VERSION, "kind": "FROZEN_PREDICTION", "prediction_id": prediction_id,
              "symbol": symbol, "market": market, "stream": stream, "timezone": ZONES[market],
              "direction": direction, "prediction_frozen_at": frozen_at, "producer": producer,
              "event": event, "features": {"reference": reference, "atr14": atr}, "event_confidence": event_confidence,
              "calendar": deepcopy(calendar)}
    if prediction_features is not None:
        result["prediction_features"] = deepcopy(prediction_features)
    result["sample_id"] = digest({"prediction_id": prediction_id, "event": EVENT, "horizon": h})
    return stamp(result)

def validate_frozen(value):
    verify(value)
    expected = freeze(prediction_id=value["prediction_id"], symbol=value["symbol"], direction=value["direction"],
                      frozen_at=value["prediction_frozen_at"], reference=value["features"]["reference"],
                      atr=value["features"]["atr14"], calendar=value["calendar"],
                      review_session=value["event"]["horizon"]["session_date"], producer=value["producer"],
                      event_confidence=value["event_confidence"], market=value["market"], stream=value["stream"],
                      prediction_features=value.get("prediction_features"))
    if value != expected:
        raise ValueError("FROZEN_REPLAY")
    return value

def lineage(frozen):
    validate_frozen(frozen)
    return {"origin_prediction_id": frozen["prediction_id"], "origin_stream": frozen["stream"],
            "origin_horizon": frozen["event"]["horizon"], "origin_frozen_at": frozen["prediction_frozen_at"],
            "origin_event_contract": EVENT, "origin_digest": frozen["content_hash"], "sample_id": frozen["sample_id"]}

def outcome(frozen, *, close, source, revision, source_digest, available_at, session_date, report_identity=None):
    validate_frozen(frozen)
    h = frozen["event"]["horizon"]
    if session_date != h["session_date"] or aware(available_at) < aware(h["close_at"]):
        raise ValueError("OUTCOME_NOT_MATURE")
    positive(close)
    if not source or not revision or len(source_digest) != 64:
        raise ValueError("OUTCOME_PROVENANCE")
    return stamp({"schema_version": VERSION, "kind": "REALIZED_OUTCOME", "sample_id": frozen["sample_id"],
                  "prediction_digest": frozen["content_hash"], "report_identity": deepcopy(report_identity), "market": frozen["market"], "symbol": frozen["symbol"],
                  "horizon": h, "close": close, "source": source, "source_revision": revision,
                  "source_digest": source_digest, "available_at": available_at})

def assess(frozen, realized, *, observed_at):
    try:
        validate_frozen(frozen)
        h = frozen["event"]["horizon"]
        if aware(observed_at) < aware(h["close_at"]):
            return {"state": "WAITING_OUTCOME", "reason": "HORIZON_NOT_COMPLETE", "direction": None}
        if realized is None:
            return {"state": "WAITING_OUTCOME", "reason": "OUTCOME_UNAVAILABLE", "direction": None}
        verify(realized)
        expected = outcome(frozen, close=realized["close"], source=realized["source"], revision=realized["source_revision"],
                           source_digest=realized["source_digest"], available_at=realized["available_at"],
                           session_date=realized["horizon"]["session_date"], report_identity=realized["report_identity"])
        if realized != expected or aware(realized["available_at"]) > aware(observed_at):
            raise ValueError("OUTCOME_BINDING")
        direction = realized_prediction_direction(realized["close"], frozen["features"]["reference"]["value"],
                                                  frozen["features"]["atr14"]["value"])
        return {"state": "INSUFFICIENT_SAMPLE", "eligible": True, "reason": "COHORT_THRESHOLD_NOT_ASSESSED", "direction": direction,
                "direction_correct": direction == frozen["direction"],
                "confidence_status": "NOT_APPLICABLE" if frozen["event_confidence"] is None else "AVAILABLE"}
    except (ValueError, KeyError, TypeError):
        return {"state": "BLOCKED_INPUT", "reason": "INVALID_REQUIRED_EVIDENCE", "direction": None}

def unique_predictions(predictions):
    unique = {}
    for p in predictions:
        validate_frozen(p)
        sid = p["sample_id"]
        if sid in unique and unique[sid] != p:
            raise ValueError("DUPLICATE_PREDICTION_CONFLICT")
        unique[sid] = p
    return [unique[k] for k in sorted(unique)]

def evaluate_direction(predictions, outcomes, *, calendar, review_session, observed_at):
    """Component-only evaluation; no weight redistribution or fabricated aggregate."""
    validate_calendar(calendar, calendar["market"])
    completed = [r["session_date"] for r in calendar["days"] if r["state"] in {"NORMAL", "EARLY_CLOSE"}
                 and r["session_date"] <= review_session and aware(r["close_at"]) <= aware(observed_at)]
    by_day = {}
    if len({p.get("symbol") for p in predictions}) > 1:
        raise ValueError("MIXED_SYMBOL_COHORT")
    for p in unique_predictions(predictions):
        if p["market"] != calendar["market"] or p["calendar"]["content_hash"] != calendar["content_hash"]:
            raise ValueError("CALENDAR_IDENTITY")
        by_day.setdefault(p["event"]["horizon"]["session_date"], []).append(p)
    evidence = {}
    for day in completed[-10:]:
        candidates = by_day.get(day, [])
        if len(candidates) != 1:
            evidence[day] = {"state": "INSUFFICIENT_SAMPLE", "reason": "MISSING_OR_AMBIGUOUS_SESSION"}
            continue
        p = candidates[0]
        evidence[day] = assess(p, outcomes.get(p["sample_id"]), observed_at=observed_at)
        evidence[day]["sample_id"] = p["sample_id"]
    windows = {}
    for n in (3,10):
        days = completed[-n:]
        eligible = [evidence[d] for d in days if evidence[d].get("eligible") is True]
        ready = len(days) == len(eligible) == n
        windows[str(n)] = {"sample_size": len(eligible), "required": n, "score": sum(100*e["direction_correct"] for e in eligible)/n if ready else None}
    ready = all(w["score"] is not None for w in windows.values())
    from app.evaluation.offline_review_evaluators import load_contract
    weights = load_contract()["weights_percent"]["time"]
    return {"state": "EVALUATED" if ready else "INSUFFICIENT_SAMPLE",
            "admission_state": "READY_FOR_EVALUATION" if ready else "INSUFFICIENT_SAMPLE", "component": "prediction.trend",
            "score": windows["3"]["score"]*weights["last_3_sessions"]/100 + windows["10"]["score"]*weights["last_10_sessions"]/100 if ready else None,
            "windows": windows, "evidence": evidence, "prediction_accuracy_score": None,
            "improvement": "NOT_APPLICABLE", "strategy": "INSUFFICIENT_SAMPLE",
            "confidence": "NOT_APPLICABLE", "aggregate_reweighted": False}

