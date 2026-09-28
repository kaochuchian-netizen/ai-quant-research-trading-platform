"""253 native prediction: US inputs, shared governed MA rule, no actions/network.
Observations and predictions live under the existing window archive owner.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import re
import signal
import threading
from zoneinfo import ZoneInfo
from app.evaluation.direction_signal import moving_average_direction
from app.evaluation.production_evidence import feature, freeze, positive, verify
from app.evaluation.prediction_regression_contract import aware, stamp
from app.evaluation.offline_report_projection import digest
from app.evaluation.session_calendar import load_calendar, session

PRODUCER = "US_PREOPEN_SESSION_DIRECTION_V1"
VERSION = "us_preopen_session_direction_v1"
STREAM = "us_pre_market_2000"
ROOT = Path(__file__).resolve().parents[2]

def symbol_valid(symbol):
    return isinstance(symbol,str) and re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,14}",symbol) is not None

def wilder(rows):
    if len(rows)<15:
        raise ValueError("INSUFFICIENT_OHLCV")
    trs=[max(r["high"]-r["low"],abs(r["high"]-prev["close"]),abs(r["low"]-prev["close"])) for prev,r in zip(rows,rows[1:])]
    value=sum(trs[:14])/14
    for tr in trs[14:]:
        value=(value*13+tr)/14
    return positive(value)

def predict(observation, calendar, *, frozen_at):
    """Replay uses recorded inputs only; no current clock."""
    verify(observation)
    if not symbol_valid(observation["symbol"]) or observation["source"]!="Yahoo Finance / yfinance":
        raise ValueError("SOURCE")
    day=observation["review_session"]
    h=session(calendar,"US",day)
    if not aware(observation["available_at"])<=aware(frozen_at)<aware(h["open_at"]):
        raise ValueError("NOT_PREOPEN")
    if aware(frozen_at).astimezone(ZoneInfo("America/New_York")).date().isoformat()!=day:
        raise ValueError("SESSION_IDENTITY")
    positive(observation["reference_price"])
    if aware(observation["reference_as_of"])>aware(observation["available_at"]):
        raise ValueError("FUTURE_REFERENCE")
    rows=observation["rows"]
    if rows!=sorted(rows,key=lambda r:r["date"]) or len({r["date"] for r in rows})!=len(rows):
        raise ValueError("BAR_ORDER")
    sessions={r["session_date"]:r for r in calendar["days"]}
    for r in rows:
        bar=sessions.get(r["date"])
        if bar is None or bar["state"] not in {"NORMAL","EARLY_CLOSE"}:
            raise ValueError("BAR_SESSION")
        if r["date"]>=day or aware(bar["close_at"])>aware(observation["available_at"]):
            raise ValueError("FUTURE_BAR")
        if positive(r["high"])<positive(r["low"]) or not r["low"]<=positive(r["close"])<=r["high"]:
            raise ValueError("BAR_VALUES")
    if len(rows)<15:
        return stamp({"schema_version":VERSION,"status":"NO_FORECAST","reason":"INSUFFICIENT_LOOKBACK",
                      "source":deepcopy(observation),"frozen_at":frozen_at,"producer":PRODUCER,"calendar":deepcopy(calendar)})
    # Require the latest completed authoritative session, never silently use stale history.
    prior=[r["session_date"] for r in calendar["days"] if r["state"] in {"NORMAL","EARLY_CLOSE"} and r["session_date"]<day]
    if not prior or rows[-1]["date"]!=prior[-1]:
        raise ValueError("STALE_HISTORY")
    ma5=sum(r["close"] for r in rows[-5:])/5
    ma10=sum(r["close"] for r in rows[-10:])/10
    raw=moving_average_direction(ma5,ma10)
    direction={"bullish":"UP","bearish":"DOWN"}.get(raw)
    common={"schema_version":VERSION,"producer":PRODUCER,"source":deepcopy(observation),
            "frozen_at":frozen_at,"calendar":deepcopy(calendar),"prediction_rule":"tw_ohlcv_range_direction_v2.directional_branches",
            "ma5":ma5,"ma10":ma10,"direction":direction}
    if direction is None:
        return stamp({**common,"status":"NO_FORECAST","reason":"NO_DIRECTIONAL_MA_SIGNAL"})
    as_of=session(calendar,"US",rows[-1]["date"])["close_at"]
    kwargs=dict(source=observation["source"],revision=observation["content_hash"],
                source_digest=observation["content_hash"],available_at=observation["available_at"])
    ref=feature("reference_price",positive(observation["reference_price"]),as_of=observation["reference_as_of"],
                producer="existing_us_quote",**kwargs)
    atr=feature("atr14",wilder(rows),as_of=as_of,producer="WILDER_14_COMPLETED_POINT_IN_TIME",**kwargs)
    fs={name:feature(name,value,as_of=as_of,producer=VERSION,**kwargs) for name,value in (("ma5",ma5),("ma10",ma10))}
    identity=digest({"producer":PRODUCER,"symbol":observation["symbol"],"session":day,
                     "observation":observation["content_hash"],"frozen_at":frozen_at})
    f=freeze(prediction_id=identity,symbol=observation["symbol"],direction=direction,frozen_at=frozen_at,
             reference=ref,atr=atr,calendar=calendar,review_session=day,producer=PRODUCER,
             market="US",stream=STREAM,prediction_features=fs)
    return stamp({**common,"status":"FROZEN","frozen":f,"reason":None})

def receipt_key(symbol,day):
    return digest({"producer":PRODUCER,"symbol":symbol,"session":day})

def capture_existing(symbol, quote, history, day, window, *, root=ROOT, clock=None):
    """Only caller-owned already fetched data. Never call market-data clients."""
    from app.dashboard.production_evidence_archive import publish
    if not symbol_valid(symbol):
        raise ValueError("SYMBOL")
    calendar=load_calendar("US")
    session(calendar,"US",day)
    clock=clock or (lambda:datetime.now(timezone.utc).isoformat())
    observed=clock()
    if aware(observed).astimezone(ZoneInfo("America/New_York")).date().isoformat()<day:
        raise ValueError("SESSION_IDENTITY")
    directory=Path(root)/"artifacts/archive/window_snapshots/us"/window/day/".frozen"
    key=receipt_key(symbol,day)
    target=directory/(key+".json")
    if window==STREAM and target.exists():
        verify(json.loads(target.read_text()))
        return
    attempt=None
    if window==STREAM:
        attempt=stamp({"schema_version":VERSION,"kind":"US_NATIVE_RECEIPT","symbol":symbol,"review_session":day,
                       "capture":stamp({"schema_version":VERSION,"status":"BLOCKED_INPUT","reason":"CAPTURE_NOT_COMPLETED","producer":PRODUCER})})
        publish(directory/(digest({"attempt":key})+".json"),attempt)
    rows=[]
    if history is None:
        raise ValueError("MISSING_HISTORY")
    # Limit the retained existing daily source; outside snapshot coverage is not inferred.
    sessions={r["session_date"]:r for r in calendar["days"]}
    for index,r in history.tail(260).iterrows():
        date=index.date().isoformat()
        if date<calendar["coverage_start"]:
            continue
        bar=sessions.get(date)
        if bar is None or bar["state"] not in {"NORMAL","EARLY_CLOSE"}:
            raise ValueError("BAR_SESSION")
        if aware(bar["close_at"])>aware(observed):
            continue
        rows.append({"date":date,"high":positive(float(r["High"])),"low":positive(float(r["Low"])),"close":positive(float(r["Close"]))})
    observation=stamp({"schema_version":VERSION,"kind":"US_MARKET_OBSERVATION","symbol":symbol,"review_session":day,
                       "source":"Yahoo Finance / yfinance","source_version":"existing_fetch_symbol_daily_auto_adjust_false",
                       "reference_price":quote.get("last_price"),"reference_as_of":quote.get("market_data_as_of"),
                       "available_at":observed,"rows":rows,"quote_digest":digest(quote)})
    # Same archive, not a second market-data acquisition system.
    publish(directory/(observation["content_hash"]+".json"),observation)
    if window==STREAM:
        try:
            # Compute the forecast before assigning its freeze timestamp.
            # The second pure call binds/replays the already computed signal.
            computed=predict(observation,calendar,frozen_at=observed)
            frozen_at=clock()
            value=predict(observation,calendar,frozen_at=frozen_at)
            if (computed["status"],computed.get("direction")) != (value["status"],value.get("direction")):
                raise ValueError("PREDICTION_REPLAY")
        except (ValueError,KeyError,TypeError):
            value=stamp({"schema_version":VERSION,"status":"BLOCKED_INPUT","reason":"NATIVE_INPUT_INVALID",
                         "source":observation,"producer":PRODUCER})
        publish(target,stamp({"schema_version":VERSION,"kind":"US_NATIVE_RECEIPT","symbol":symbol,
                              "review_session":day,"capture":value}))

def capture_safely(symbol, quote, history, day, window, *, enabled, root=ROOT):
    """Two-second best-effort capture; skip when caller owns an alarm/thread."""
    import os
    from app.evaluation.prediction_capture import capture_permitted
    if not enabled or not capture_permitted(dry_run=False,environment_keys=os.environ):
        return
    if threading.current_thread() is not threading.main_thread() or signal.getitimer(signal.ITIMER_REAL)[0]:
        return
    old=signal.getsignal(signal.SIGALRM)
    def expired(*_):
        raise TimeoutError("US_CAPTURE_TIMEOUT")
    try:
        signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,2)
        capture_existing(symbol,quote,history,day,window,root=root)
    except Exception:
        logging.getLogger(__name__).warning("us_session_direction: SHADOW_CAPTURE_FAILED")
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
