"""254 pure daily/session review; shared evaluators, no clock, network or actions."""
from copy import deepcopy
from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from app.evaluation.prediction_regression_contract import aware, stamp
from app.evaluation.offline_report_projection import digest, evidence_chain, realized_effect
from app.evaluation.offline_review_evaluators import evaluate_stock, load_contract
from app.evaluation.production_evidence import verify, validate_frozen, unique_predictions, assess, evaluate_direction
from app.evaluation.session_calendar import latest_completed_session, validate_calendar

VERSION = "daily_evaluation_integration_v1"
STREAM = "daily_evaluation_1700"
ORIGINS = {"TW": "pre_open_0700", "US": "us_pre_market_2000"}

def canonical_cutoff(report_date):
    return datetime.combine(date.fromisoformat(report_date), time(17), ZoneInfo("Asia/Taipei")).isoformat()

def calendar_binding(c):
    return {k:deepcopy(c[k]) for k in ("market","schema_version","version","revision","source","coverage_start","coverage_end","content_hash")}

def admitted(records, market, cutoff, review_session):
    predictions, bindings, exclusions = [], {}, []
    for record in sorted(records, key=lambda r:r.get("content_hash","")):
        verify(record)
        if record.get("kind") != "REPORT_EVIDENCE":
            raise ValueError("REPORT_EVIDENCE_KIND")
        identity=record["report_identity"]
        if (record.get("input_kind") != "PRODUCTION_DERIVED" or record.get("synthetic") is True
            or identity.get("run_kind") != "scheduled" or identity.get("market") != market
            or identity.get("window") != ORIGINS[market]):
            exclusions.append({"digest":record["content_hash"],"reason":"NON_CANONICAL_ORIGIN"})
            continue
        for r in record["records"]:
            if (r.get("capability") != "NATIVE_DIRECTION" or r.get("direction_sample_count") != 1
                or r.get("state") in {"HISTORICAL_INELIGIBLE","BLOCKED_INPUT"}
                or r.get("direction_status") == "NO_FORECAST" or r.get("frozen") is None):
                exclusions.append({"digest":record["content_hash"],"symbol":r.get("symbol"),"reason":"NOT_INDEPENDENT_FORECAST"})
                continue
            f=r["frozen"];validate_frozen(f)
            if (f["market"] != market or f["stream"] != ORIGINS[market] or f["symbol"] != r["symbol"]
                or f["event"]["horizon"]["session_date"] != identity["effective_trading_date"]):
                raise ValueError("ORIGIN_BINDING")
            if aware(f["prediction_frozen_at"]) > aware(cutoff) or f["event"]["horizon"]["session_date"] > review_session:
                continue
            predictions.append(f)
            bindings.setdefault(f["sample_id"],[]).append({"report_identity":deepcopy(identity),"report_digest":record["report_digest"],"evidence_digest":record["content_hash"]})
    return unique_predictions(predictions), bindings, exclusions

def select_outcomes(predictions, candidates, cutoff):
    by_id={}
    for o in candidates:
        verify(o)
        if o.get("kind") != "REALIZED_OUTCOME":
            raise ValueError("OUTCOME_KIND")
        if aware(o["available_at"]) <= aware(cutoff):
            by_id.setdefault(o["sample_id"],[]).append(o)
    result={}
    for f in predictions:
        options=by_id.get(f["sample_id"],[])
        for o in options:
            if assess(f,o,observed_at=cutoff).get("eligible") is not True:
                raise ValueError("OUTCOME_BINDING")
        if len({o["close"] for o in options})>1:
            raise ValueError("AMBIGUOUS_OUTCOME_REVISION")
        if options:
            result[f["sample_id"]]=min(options,key=lambda o:(aware(o["available_at"]),o["content_hash"]))
    return result

def evaluator_rows(predictions, outcomes, cutoff):
    """Partial 251B rows: never invent target/range/confidence/fix/strategy."""
    rows=[]
    for p in predictions:
        o=outcomes.get(p["sample_id"])
        if not o:
            continue
        h=p["event"]["horizon"]; fields={}
        for name,feature in (("reference_price",p["features"]["reference"]),("atr14",p["features"]["atr14"])):
            fields[name]={"classification":"AVAILABLE","role":"signal","value":feature["value"],
                          "as_of":feature["as_of"],"available_at":feature["available_at"],"source_ref":feature["content_hash"]}
        for name,value in (("trend",p["direction"]),("atr_method","WILDER_14_COMPLETED_POINT_IN_TIME")):
            fields[name]={"classification":"AVAILABLE","role":"signal","value":value,"as_of":p["prediction_frozen_at"],
                          "available_at":p["prediction_frozen_at"],"source_ref":p["content_hash"]}
        for name,value in (("close",o["close"]),("outcome_horizon_sessions",1)):
            fields[name]={"classification":"AVAILABLE","role":"outcome","value":value,"as_of":h["close_at"],
                          "available_at":o["available_at"],"source_ref":o["content_hash"]}
        rows.append({"market":p["market"],"symbol":p["symbol"],"strategy_id":"daily_tactical","horizon_sessions":1,
                     "session_date":h["session_date"],"prediction_at":p["prediction_frozen_at"],
                     "outcome_closed_at":h["close_at"],"evaluation_at":cutoff,"fields":fields})
    return rows

def build_market(market, calendar, records, outcomes, cutoff):
    review=latest_completed_session(calendar,market,cutoff)["session_date"]
    predictions,bindings,exclusions=admitted(records,market,cutoff,review)
    selected=select_outcomes(predictions,outcomes,cutoff)
    symbols=sorted({r.get("symbol") for v in records if v.get("report_identity",{}).get("market")==market
                    for r in v.get("records",[]) if r.get("symbol")})
    stocks={}
    for symbol in symbols:
        ps=[p for p in predictions if p["symbol"]==symbol]
        os={p["sample_id"]:selected[p["sample_id"]] for p in ps if p["sample_id"] in selected}
        direction=evaluate_direction(ps,os,calendar=calendar,review_session=review,observed_at=cutoff)
        evaluation=evaluate_stock(evaluator_rows(ps,os,cutoff),market=market,symbol=symbol,strategy_id="daily_tactical",
                                  horizon_sessions=1,report_date=review,calendar=calendar,review_session=review,evaluated_at=cutoff)
        empty={"evidence_records":[],"linkage_refs":{"finding":None,"fix":None,"evaluation":None},"evaluation":evaluation}
        stocks[symbol]={"direction_component":direction,"evaluation":evaluation,
                        "evidence_chain":evidence_chain(empty),"realized_effect":realized_effect(empty),
                        "finding_evidence":{"status":"DIAGNOSTIC_ONLY","early_window":direction["windows"]["3"],
                                            "persistent_window":direction["windows"]["10"],"formal_fix_linkage":None},
                        "sample_reviews":{p["sample_id"]:{"prediction_digest":p["content_hash"],"origin":bindings[p["sample_id"]],
                           "frozen_reference":p["features"]["reference"],"frozen_atr14":p["features"]["atr14"],
                           "event":p["event"],"prediction_direction":p["direction"],
                           "outcome_digest":os.get(p["sample_id"],{}).get("content_hash"),
                           "assessment":assess(p,os.get(p["sample_id"]),observed_at=cutoff)} for p in ps}}
    return {"status":"VALID","review_session":review,"calendar":calendar_binding(calendar),"stocks":stocks,"exclusions":exclusions}

def build_daily(report_date, inputs, predecessor=None):
    cutoff=canonical_cutoff(report_date)
    if set(inputs)!={"TW","US"}:
        raise ValueError("MARKET_INPUT_SHAPE")
    markets={}
    for market in ("TW","US"):
        packet=inputs[market]
        try:
            if packet.get("prerequisite_error"):
                raise ValueError("INPUT_PREREQUISITE")
            markets[market]=build_market(market,packet["calendar"],packet["records"],packet["outcomes"],cutoff)
        except (ValueError,KeyError,TypeError):
            markets[market]={"status":"BLOCKED_INPUT","reason":"INVALID_CALENDAR_OR_EVIDENCE"}
    from app.evaluation.offline_report_projection import contract as projection_contract, EVALUATOR_VERSION
    contracts={"251A":digest(load_contract()),"251B":EVALUATOR_VERSION,"251C":digest(projection_contract()),
               "252":"production_evidence_accumulation_v1","254":VERSION}
    identity=digest({"schema_version":VERSION,"report_date":report_date,"input_digest":digest(inputs),"contracts":contracts})
    comparison={"status":"NO_PREDECESSOR"}
    if predecessor is not None:
        try:
            verify(predecessor)
            if predecessor.get("schema_version") != VERSION or predecessor.get("kind") != "DAILY_PREDECESSOR_PROOF":
                raise ValueError("PREDECESSOR_SCHEMA")
            prior_core=build_daily(predecessor["report_date"],predecessor["inputs"])
            if any(prior_core[k]!=predecessor[k] for k in ("identity","markets","stream")) or predecessor["core_digest"]!=prior_core["content_hash"]:
                raise ValueError("PREDECESSOR_REPLAY")
            if predecessor["report_date"]>=report_date or predecessor["stream"]!=STREAM:
                raise ValueError("PREDECESSOR_IDENTITY")
            comparison={"status":"BOUND","relationship":"PRIOR_IMMUTABLE_DAILY_REVIEW",
                        "current_identity":identity,"predecessor_identity":predecessor["identity"],
                        "predecessor_hash":predecessor["core_digest"],"predecessor_schema":predecessor["schema_version"],
                        "components":{}}
            for market in ("TW","US"):
                previous=predecessor["markets"][market]
                for symbol,current in markets[market].get("stocks",{}).items():
                    old=previous.get("stocks",{}).get(symbol)
                    comparable=old is not None and old["direction_component"]["state"]==current["direction_component"]["state"]=="EVALUATED"
                    comparison["components"][market+":"+symbol]={"status":"COMPARED" if comparable else "INSUFFICIENT_COMPARISON",
                        "direction_score_delta":current["direction_component"]["score"]-old["direction_component"]["score"] if comparable else None,
                        "predecessor_component_evidence":deepcopy(old)}
        except (ValueError,KeyError,TypeError,RecursionError):
            comparison={"status":"REJECTED","reason":"PREDECESSOR_INTEGRITY"}
    return stamp({"schema_version":VERSION,"kind":"DAILY_EVALUATION","stream":STREAM,"identity":identity,
                  "report_date":report_date,"canonical_cutoff":cutoff,"schedule_timezone":"Asia/Taipei",
                  "input_digest":digest(inputs),"evaluator_contracts":contracts,"inputs":deepcopy(inputs),"markets":markets,"comparison":comparison,
                  "predecessor":deepcopy(predecessor),"thresholds":{"3":3,"10":10},"lifecycle_mutation":False,
                  "notification":False,"status":"BLOCKED_INPUT" if any(m["status"]=="BLOCKED_INPUT" for m in markets.values()) else "VALID"})

def replay(value):
    verify(value)
    if value.get("schema_version")!=VERSION or value.get("kind")!="DAILY_EVALUATION":
        raise ValueError("DAILY_SCHEMA")
    if value!=build_daily(value["report_date"],value["inputs"],value["predecessor"]):
        raise ValueError("DAILY_REPLAY")
    return value

def predecessor_proof(value):
    """Bounded replay proof: pins the immutable semantic core, not a mutable latest."""
    replay(value)
    core=build_daily(value["report_date"],value["inputs"])
    return stamp({"schema_version":VERSION,"kind":"DAILY_PREDECESSOR_PROOF",
                  "stream":STREAM,"identity":value["identity"],"report_date":value["report_date"],
                  "source_artifact_hash":value["content_hash"],"core_digest":core["content_hash"],
                  "inputs":deepcopy(value["inputs"]),"markets":deepcopy(value["markets"])})
