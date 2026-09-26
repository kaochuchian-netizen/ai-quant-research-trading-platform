"""Session-based shadow projection. Pure evaluation, no network/delivery/action clients."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from app.evaluation.offline_report_projection import digest, evidence_chain, realized_effect, SCORES
from app.evaluation.offline_review_evaluators import evaluate_stock
from app.evaluation.prediction_regression_contract import aware, stamp
from app.evaluation.session_calendar import CalendarError, load_calendar, session, ZONES

VERSION = "ai_dev_251d_session_shadow_v1"
WINDOWS = {"TW": ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"),
           "US": ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630")}

def source_packet(snapshot):
    """Retain only explicit canonical identity and sanitized admission diagnostics.
    Missing point-in-time feature/outcome mapping remains missing, never inferred.
    Original archive remains sole owner of raw report content.
    """
    market, window, day = snapshot["market"], snapshot["window"], snapshot["effective_trading_date"]
    if market not in WINDOWS or window not in WINDOWS[market]:
        raise ValueError("SOURCE_STREAM")
    payload = snapshot["payload"]
    keys = ("structured_pre_open_cards", "structured_intraday_cards", "structured_pre_close_cards", "structured_review_cards") if market == "TW" else ("items", "structured_intraday_cards")
    candidates = next((payload[k] for k in keys if isinstance(payload.get(k), list)), [])
    symbols = sorted({str(r.get("symbol") or r.get("stock_id") or r.get("code")) for r in candidates
                      if isinstance(r, dict) and (r.get("symbol") or r.get("stock_id") or r.get("code"))})
    if len(symbols) > 500 or any(len(s) > 32 or not all(c.isalnum() or c in "._-" for c in s) for s in symbols):
        raise ValueError("SOURCE_SYMBOL")
    return {"source": {k: snapshot[k] for k in ("snapshot_id", "schema_version", "revision", "market", "window", "effective_trading_date", "generated_at", "run_kind")},
            "source_digest": digest(snapshot), "review_session": day, "timezone": ZONES[market],
            "evaluated_at": snapshot["generated_at"], "symbols": symbols,
            "rows": [], "source_coverage": {"prediction": "PARTIAL", "feature": "AMBIGUOUS", "outcome": "MISSING", "fix": "MISSING"},
            "reason_codes": ["POINT_IN_TIME_MAPPING_NOT_ADMITTED", "OUTCOME_COHORT_NOT_ADMITTED", "NO_IMPLEMENTED_FIX"],
            "adapter_version": VERSION}

def build_shadow(packet, calendar):
    packet = deepcopy(packet)
    market = packet["source"]["market"]
    root = Path(__file__).resolve().parents[2]
    contract_digest = digest(json.loads((root / "config/governance/production_shadow_contract_v1.json").read_text()))
    result = {"schema_version": VERSION, "contract_digest": contract_digest, "contract_version": VERSION,
              "report_identity": deepcopy(packet["source"]), "report_content_digest": packet["source_digest"],
              "review_session": packet["review_session"], "timezone": packet["timezone"],
              "evaluation_inputs": packet, "calendar": deepcopy(calendar),
              "evaluator_contract_version": "ai_dev_251b_session_context_v2",
              "component_evidence": {}, "evidence_chain": {}, "realized_effect": {},
              "status": "BLOCKED_INPUT", "reason_codes": [], "scored_predecessor_eligible": False,
              "comparison": {"status": "NO_PREDECESSOR", "predecessor_ref": None},
              "lifecycle_mutation": False, "strategy_mutation": False, "delivery_mutation": False,
              "generation": {"adapter": VERSION, "evaluation_at": packet["evaluated_at"], "mode": "SHADOW"}}
    try:
        record = session(calendar, market, packet["review_session"])
        if aware(packet["evaluated_at"]) < aware(record["close_at"]):
            result.update(status="PENDING", reason_codes=["SESSION_INCOMPLETE"])
        elif not packet["symbols"]:
            result["reason_codes"] = ["REPORT_SYMBOL_IDENTITY_MISSING"]
        else:
            for symbol in packet["symbols"]:
                evaluation = evaluate_stock(packet["rows"], market=market, symbol=symbol, strategy_id="daily_tactical",
                    horizon_sessions=1, report_date=packet["review_session"], calendar=calendar,
                    review_session=packet["review_session"], evaluated_at=packet["evaluated_at"])
                result["component_evidence"][symbol] = evaluation
                view = {"report_id": packet["source"]["snapshot_id"], "identity": {"market": market, "symbol": symbol, "strategy_id": "daily_tactical"},
                        "evaluation": evaluation, "evidence_records": [], "linkage_refs": {"finding": None, "fix": None, "evaluation": None}}
                result["evidence_chain"][symbol] = evidence_chain(view)
                result["realized_effect"][symbol] = realized_effect(view)
            ready = all(e["user_facing"][key]["score"] is not None for e in result["component_evidence"].values() for key in SCORES)
            result.update(status="EVALUATED" if ready else "INSUFFICIENT_SAMPLE",
                          reason_codes=[] if ready else packet["reason_codes"],
                          scored_predecessor_eligible=ready and packet["source"]["run_kind"] == "scheduled")
    except CalendarError as exc:
        result["reason_codes"] = [str(exc)]
    return stamp(result)

def reference(value):
    return {"schema_version": value["schema_version"], "report_identity": value["report_identity"],
            "content_hash": value["content_hash"]}

def validate_shadow(value, *, comparison=True):
    if value.get("schema_version") != VERSION or value.get("content_hash") != digest({k:v for k,v in value.items() if k != "content_hash"}):
        raise ValueError("SHADOW_DIGEST_OR_VERSION")
    base = build_shadow(value["evaluation_inputs"], value["calendar"])
    if set(value) != set(base):
        raise ValueError("SHADOW_SCHEMA")
    for key in base:
        if key not in {"comparison", "content_hash"} and base[key] != value.get(key):
            raise ValueError("SHADOW_REPLAY_MISMATCH")
    if comparison:
        comp = value["comparison"]
        if comp["status"] == "NO_PREDECESSOR":
            if comp != {"status": "NO_PREDECESSOR", "predecessor_ref": None}:
                raise ValueError("COMPARISON_SHAPE")
        elif comp["status"] == "REJECTED":
            if set(comp) != {"status", "predecessor_ref", "reason"} or comp["predecessor_ref"] is not None or comp["reason"] not in {"PREDECESSOR_INTEGRITY", "CORRUPTED_PREDECESSOR"}:
                raise ValueError("COMPARISON_SHAPE")
        elif comp["status"] in {"BOUND", "INSUFFICIENT_COMPARISON"}:
            prior = comp["predecessor_evidence"]
            validate_shadow(prior, comparison=False)
            if comp["predecessor_ref"] != reference(prior) or comp["component_evidence"] != prior["component_evidence"]:
                raise ValueError("PREDECESSOR_REPLAY")
            expected = bind_predecessor(base, prior)
            if expected != value:
                raise ValueError("COMPARISON_REPLAY")
            if not prior["scored_predecessor_eligible"] or value["report_identity"]["run_kind"] != "scheduled":
                raise ValueError("PREDECESSOR_NOT_ELIGIBLE")
            if any(value["report_identity"][k] != prior["report_identity"][k] for k in ("market","window")) or prior["review_session"] >= value["review_session"]:
                raise ValueError("PREDECESSOR_STREAM_OR_SESSION")
        else:
            raise ValueError("COMPARISON_STATUS")
    return True

def bind_predecessor(current, predecessor=None):
    validate_shadow(current)
    result = deepcopy(current)
    if predecessor is not None:
        try:
            validate_shadow(predecessor)
            a,b = current["report_identity"], predecessor["report_identity"]
            if not predecessor["scored_predecessor_eligible"] or a["run_kind"] != "scheduled":
                raise ValueError("PREDECESSOR_NOT_ELIGIBLE")
            if any(a[k] != b[k] for k in ("market","window")) or predecessor["review_session"] >= current["review_session"]:
                raise ValueError("PREDECESSOR_STREAM_OR_SESSION")
            result["comparison"] = {"status": "BOUND" if current["scored_predecessor_eligible"] else "INSUFFICIENT_COMPARISON",
                                    "predecessor_ref": reference(predecessor),
                                    "component_evidence": deepcopy(predecessor["component_evidence"]),
                                    "predecessor_evidence": deepcopy(predecessor),
                                    "relationship": "PRIOR_SUCCESSFUL_SCORED_SESSION_SAME_STREAM",
                                    "scores": {symbol: {key: {
                                        "before": predecessor["component_evidence"][symbol]["user_facing"][key]["score"],
                                        "after": current["component_evidence"][symbol]["user_facing"][key]["score"],
                                        "delta": (current["component_evidence"][symbol]["user_facing"][key]["score"] - predecessor["component_evidence"][symbol]["user_facing"][key]["score"])
                                            if current["component_evidence"][symbol]["user_facing"][key]["score"] is not None else None}
                                        for key in SCORES}
                                        for symbol in sorted(set(current["component_evidence"]) & set(predecessor["component_evidence"]))}}
        except (ValueError, TypeError, KeyError):
            result["comparison"] = {"status": "REJECTED", "predecessor_ref": None, "reason": "PREDECESSOR_INTEGRITY"}
    return stamp(result)
