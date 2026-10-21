"""Frozen public forecast contract, distinct from trade-plan/research scores.

Pure functions: no acquisition, persistence, notification or learning writes.
The public forecast is scored with the existing TW open/close tolerance and
range-endpoint overlap rules, never with a tactical no-trade eligibility flag.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
import math
import re

KEY = "frozen_delivery_prediction_v1"
EVALUATION_KEY = "delivery_prediction_evaluation_v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def number(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("DELIVERY_FORECAST_INVALID_NUMBER")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("DELIVERY_FORECAST_INVALID_NUMBER")
    return value


def freeze(card, presentation):
    """Freeze exactly the fields used by the 07:00 public renderer."""
    symbol = str(card.get("symbol") or card.get("stock_id") or "")
    session = str(card.get("trading_date") or card.get("effective_trading_date") or "")
    date.fromisoformat(session)
    if not re.fullmatch(r"[0-9]{4,6}", symbol):
        raise ValueError("DELIVERY_FORECAST_SYMBOL_INVALID")
    interval = presentation.get("today_range") or {}
    low, high = number(interval.get("predicted_low")), number(interval.get("predicted_high"))
    if (low is None) != (high is None) or (low is not None and (low <= 0 or low > high)):
        raise ValueError("DELIVERY_FORECAST_INTERVAL_INVALID")
    direction = presentation.get("direction")
    direction = "neutral" if direction == "range_bound" else direction
    if direction not in {"bullish", "bearish", "neutral"}:
        direction = None
    unavailable = card.get("availability_status") == "unavailable" or bool(card.get("failure_category"))
    if unavailable:
        direction = low = high = None
    if (direction is not None or low is not None) and not presentation.get("prediction_id"):
        raise ValueError("DELIVERY_PREDICTION_ID_MISSING")
    product = card.get("tw_preopen_product_intelligence_v1") or {}
    if product and not unavailable:
        product_direction = str(product.get("today_direction") or "").lower()
        product_direction = {"sideways": "neutral", "range_bound": "neutral"}.get(product_direction, product_direction)
        if (product_direction, number(product.get("predicted_low")), number(product.get("predicted_high"))) != (direction, low, high):
            raise ValueError("DELIVERY_PUBLIC_SURFACE_MISMATCH")
    value = {"schema_version": KEY, "market": "TW", "window": "pre_open_0700",
             "symbol": symbol, "trading_date": session,
             "prediction_id": presentation.get("prediction_id"),
             "direction": direction, "low": low, "high": high,
             "source_field": "prediction_presentation_v1",
             "representation_hash": digest(presentation),
             "reason_code": "PREDICTION_NOT_PUBLISHED" if unavailable else "NO_PUBLISHED_FORECAST" if direction is None and low is None else None}
    value["digest"] = digest(value)
    return value


def validate_projection(value):
    if not isinstance(value, dict) or value.get("schema_version") != KEY:
        raise ValueError("DELIVERY_PROJECTION_SCHEMA")
    raw = {k: v for k, v in value.items() if k != "digest"}
    if value.get("digest") != digest(raw) or value.get("market") != "TW" or value.get("window") != "pre_open_0700":
        raise ValueError("DELIVERY_PROJECTION_DIGEST")
    date.fromisoformat(value["trading_date"])
    low, high = number(value.get("low")), number(value.get("high"))
    if (low is None) != (high is None) or (low is not None and (low <= 0 or low > high)):
        raise ValueError("DELIVERY_FORECAST_INTERVAL_INVALID")
    if value.get("direction") not in {None, "bullish", "bearish", "neutral"}:
        raise ValueError("DELIVERY_FORECAST_DIRECTION_INVALID")
    return value


def snapshot_identity(snapshot, *, window, session):
    from app.dashboard.window_snapshot_archive import admission_errors
    if admission_errors(snapshot) or snapshot.get("market") != "TW" or snapshot.get("window") != window or snapshot.get("effective_trading_date") != session:
        raise ValueError("DELIVERY_SNAPSHOT_IDENTITY")
    if snapshot.get("snapshot_id") != digest({k: v for k, v in snapshot.items() if k != "snapshot_id"}):
        raise ValueError("DELIVERY_SNAPSHOT_HASH")
    return {"snapshot_id": snapshot["snapshot_id"], "revision": snapshot["revision"],
            "payload_hash": digest(snapshot["payload"]), "trading_date": session}


def bind_universe(snapshot, *, session, allow_legacy=False):
    """Bind the entire admitted natural 07:00 universe, without filtering.

    Legacy reconstruction is explicit and restricted to isolated correction;
    normal production collection requires the stored projection.
    """
    identity = snapshot_identity(snapshot, window="pre_open_0700", session=session)
    if snapshot.get("run_kind") != "scheduled" or snapshot.get("manual_rerun"):
        raise ValueError("DELIVERY_NATURAL_SNAPSHOT_REQUIRED")
    payload = snapshot["payload"]
    symbols = payload.get("notification_universe")
    if not isinstance(symbols, list) or not symbols or any(not isinstance(s, str) or not re.fullmatch(r"[0-9]{4,6}", s) for s in symbols) or len(symbols) != len(set(symbols)):
        raise ValueError("DELIVERY_UNIVERSE_INVALID")
    if set(payload.get("tracking_symbols") or []) != set(symbols):
        raise ValueError("DELIVERY_TRACKING_UNIVERSE_MISMATCH")
    cards = payload.get("structured_pre_open_cards") or []
    by_symbol = {str(c.get("symbol") or c.get("stock_id") or ""): c for c in cards}
    if len(cards) != len(symbols) or set(by_symbol) != set(symbols):
        raise ValueError("DELIVERY_UNIVERSE_CARD_MISMATCH")
    bound = {}
    for symbol in symbols:
        card = deepcopy(by_symbol[symbol])
        presentation = card.get("prediction_presentation_v1")
        if not isinstance(presentation, dict) or card.get("trading_date") != session:
            raise ValueError("DELIVERY_PRESENTATION_MISSING_OR_WRONG_DATE")
        expected = freeze(card, presentation)
        projection = card.get(KEY)
        if projection is None and allow_legacy:
            # Confirm the persisted public representation against its original
            # research prediction fields; never synthesize a new prediction.
            research = card.get("prediction_snapshot_v2") or {}
            interval = research.get("range_forecast") or {}
            if research.get("symbol") != symbol or research.get("effective_trading_date") != session or research.get("prediction_identity") != expected["prediction_id"] or research.get("direction_forecast") != expected["direction"] or (interval.get("low"), interval.get("high")) != (expected["low"], expected["high"]):
                raise ValueError("LEGACY_DELIVERED_REPRESENTATION_MISMATCH")
            projection = expected
        if validate_projection(projection) != expected:
            raise ValueError("DELIVERY_FROZEN_REPRESENTATION_MISMATCH")
        card[KEY] = deepcopy(projection)
        card["delivery_source_identity"] = {**identity, "universe_digest": digest(symbols), "symbol": symbol}
        bound[symbol] = card
    return symbols, bound


def evaluate(card, setup):
    projection = validate_projection(setup[KEY])
    identity = setup.get("delivery_source_identity") or {}
    symbol = str(card.get("symbol") or card.get("stock_id") or "")
    if (identity.get("snapshot_id") != card.get("source_snapshot_id")
        or card.get("prediction_snapshot_id", card.get("source_snapshot_id")) != identity.get("snapshot_id")
        or identity.get("revision") != card.get("prediction_revision", card.get("source_revision"))
        or identity.get("payload_hash") != card.get("prediction_payload_hash", card.get("parent_source_payload_hash"))
        or identity.get("trading_date") != card.get("trading_date")
        or projection["trading_date"] != card.get("trading_date")
        or identity.get("symbol") != symbol or projection["symbol"] != symbol
        or not all(identity.get(k) for k in ("snapshot_id", "revision", "payload_hash", "universe_digest"))):
        raise ValueError("DELIVERY_EVALUATION_IDENTITY_MISMATCH")
    values = [number(card.get("actual_" + k)) for k in ("open", "high", "low", "close")]
    opening, high, low, close = values
    valid = (card.get("actual_status") == "complete" and None not in values
             and 0 < low <= min(opening, close) <= max(opening, close) <= high)
    common = {"scope": "TW_FROZEN_DELIVERED_FORECAST", "identity": identity}
    if not valid:
        direction = interval = {**common, "status": "INSUFFICIENT_EVIDENCE", "result": None, "reason_code": "ACTUAL_OUTCOME_MISSING_OR_INVALID"}
    else:
        forecast = projection["direction"]
        direction = {**common, "status": "NOT_APPLICABLE", "result": "not_applicable", "reason_code": "NO_PUBLISHED_DIRECTION_FORECAST"}
        if forecast is not None:
            hit = close > opening if forecast == "bullish" else close < opening if forecast == "bearish" else abs(close - opening) / opening <= 0.005
            direction = {**common, "status": "EVALUATED", "result": "hit" if hit else "miss", "reason_code": None,
                         "forecast": forecast, "actual": "bullish" if close > opening else "bearish" if close < opening else "neutral"}
        interval = {**common, "status": "NOT_APPLICABLE", "result": "not_applicable", "reason_code": "NO_PUBLISHED_RANGE_FORECAST"}
        if projection["low"] is not None:
            # Reuse the established scoring function, without tactical
            # eligibility suppressing an independently published forecast.
            from app.reports.tw_four_window_decision import _prediction_result
            result = _prediction_result({"predicted_low": projection["low"], "predicted_high": projection["high"]}, low, high, no_trade=False)
            interval = {**common, "status": "EVALUATED", "result": result, "reason_code": None,
                        "forecast_low": projection["low"], "forecast_high": projection["high"]}
    return {"schema_version": EVALUATION_KEY, "projection_digest": projection["digest"],
            "scoring_contract": "tw_open_close_neutral_0.005_and_range_endpoint_overlap_v1",
            "actual_digest": digest({"ohlc": values, "status": card.get("actual_status"),
                                     "as_of": card.get("market_data_as_of"), "source": card.get("source_name")}),
            "direction": direction, "range": interval}


def quality(card):
    """Validate stored scoring/identity before allowing any public labels."""
    try:
        computed = evaluate(card, card)
        if computed != card.get(EVALUATION_KEY):
            raise ValueError("DELIVERY_EVALUATION_RESULT_MISMATCH")
        return computed["direction"], computed["range"]
    except (ValueError, KeyError, TypeError):
        failure = {"status": "INSUFFICIENT_EVIDENCE", "result": None,
                   "reason_code": "DELIVERY_EVALUATION_INTEGRITY_FAILED"}
        return failure, dict(failure)


def complete_results(cards, symbols, setups, failures):
    """Retain an explicit unassessable row for every missing frozen symbol."""
    indexed = {str(c.get("symbol") or c.get("stock_id") or ""): c for c in cards}
    if len(indexed) != len(cards) or set(indexed) - set(symbols):
        raise ValueError("DELIVERY_RESULT_UNIVERSE_MISMATCH")
    reasons = {str(r.get("stock_id")): str(r.get("reason")) for r in failures}
    for symbol in symbols:
        if symbol in indexed:
            continue
        setup = setups[symbol]
        identity = setup["delivery_source_identity"]
        card = {"symbol": symbol, "stock_id": symbol, "stock_name": setup.get("stock_name"),
                "trading_date": identity["trading_date"], "window": "post_close_1500",
                "source_snapshot_id": identity["snapshot_id"], "prediction_snapshot_id": identity["snapshot_id"],
                "prediction_revision": identity["revision"], "prediction_payload_hash": identity["payload_hash"],
                "prediction_source_window": "pre_open_0700", KEY: deepcopy(setup[KEY]),
                "delivery_source_identity": deepcopy(identity), "actual_status": "unavailable",
                "actual_missing_reason": reasons.get(symbol, "POST_CLOSE_CARD_NOT_GENERATED"),
                "data_status": "unavailable"}
        card[EVALUATION_KEY] = evaluate(card, card)
        indexed[symbol] = card
    return [indexed[s] for s in symbols]


def correction(pre, post, *, session, revision, expected_pre_id, expected_post_id):
    """Re-evaluate sealed official outcomes against sealed published forecasts.

    This returns a separate correction, never a replacement natural snapshot.
    Original tactical and research scores remain in the preserved source card.
    """
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ValueError("CORRECTION_REVISION_INVALID")
    if pre.get("snapshot_id") != expected_pre_id or post.get("snapshot_id") != expected_post_id:
        raise ValueError("CORRECTION_EXPECTED_IDENTITY_MISMATCH")
    post_identity = snapshot_identity(post, window="post_close_1500", session=session)
    symbols, setups = bind_universe(pre, session=session, allow_legacy=True)
    payload = post["payload"]
    cards = payload.get("structured_review_cards") or []
    by_symbol = {str(c.get("symbol") or c.get("stock_id") or ""): c for c in cards}
    if payload.get("notification_universe") != symbols or len(cards) != len(symbols) or set(by_symbol) != set(symbols):
        raise ValueError("CORRECTION_UNIVERSE_MISMATCH")
    corrected = []
    for symbol in symbols:
        original = by_symbol[symbol]
        card = deepcopy(original)
        card[KEY] = deepcopy(setups[symbol][KEY])
        card["delivery_source_identity"] = deepcopy(setups[symbol]["delivery_source_identity"])
        card[EVALUATION_KEY] = evaluate(card, setups[symbol])
        corrected.append(card)
    identity = {"schema_version": "tw_delivery_correction_v1", "session": session,
                "correction_revision": revision, "pre": setups[symbols[0]]["delivery_source_identity"],
                "post": post_identity, "universe_digest": digest(symbols),
                "evaluations_digest": digest([c[EVALUATION_KEY] for c in corrected])}
    correction_id = digest(identity)
    result = deepcopy(post)
    result["payload"] = {**deepcopy(payload), "cards": corrected, "structured_review_cards": corrected,
                         "notification_universe": symbols, "tracking_symbols": symbols,
                         "correction_provenance": identity,
                         "marker": f"{session} 15:00 更正報告（隔離驗證，未發布）"}
    result.update({"snapshot_id": correction_id, "run_kind": "isolated_correction",
                   "runtime_provenance": "isolated_correction", "admitted": False,
                   "admission_reason": "publication_requires_explicit_approval",
                   "correction_revision": revision, "parent_snapshot_id": post_identity["snapshot_id"]})
    return result
