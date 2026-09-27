"""252 immutable artifacts within the existing window archive owner."""
import json
import os
import tempfile
from pathlib import Path
from copy import deepcopy
from app.evaluation.offline_report_projection import digest
from app.evaluation.prediction_regression_contract import stamp
from app.evaluation.production_evidence import capability, lineage, validate_frozen, VERSION, verify

def publish(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("ARTIFACT_SYMLINK")
    fd, temp = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(value,out,sort_keys=True,ensure_ascii=False,separators=(",",":"))
            out.flush(); os.fsync(out.fileno())
        try:
            os.link(temp,path)
        except FileExistsError:
            if json.loads(path.read_text()) != value:
                raise ValueError("IMMUTABLE_CONFLICT")
    finally:
        os.unlink(temp)
    return path

def project(snapshot, frozen_sources=None):
    """Report binding does not alter the source payload or create forecasts."""
    from app.dashboard.window_snapshot_archive import snapshot_id, admission_errors
    if admission_errors(snapshot) or snapshot["snapshot_id"] != snapshot_id({k:v for k,v in snapshot.items() if k != "snapshot_id"}):
        raise ValueError("REPORT_INTEGRITY")
    market, stream = snapshot["market"],snapshot["window"]
    cap = capability(market,stream)
    payload = snapshot["payload"]
    keys = ("structured_pre_open_cards","structured_intraday_cards","structured_pre_close_cards","structured_review_cards") if market=="TW" else ("items",)
    cards = next((payload[k] for k in keys if isinstance(payload.get(k),list)),[])
    records = []
    for card in cards:
        symbol = str(card.get("symbol") or card.get("stock_id") or card.get("code") or "")
        native = card.get("prediction_snapshot_v2") or {}
        saved = (frozen_sources or {}).get(native.get("prediction_identity") or ("missing-native:"+symbol))
        source = None
        if saved is not None:
            try:
                verify(saved)
                if saved["native_prediction_digest"] != digest(native):
                    raise ValueError("NATIVE_PREDICTION_DIGEST")
                source = saved["capture"]
            except (ValueError,KeyError,TypeError):
                source = {"status":"BLOCKED_INPUT"}
        r = {"symbol":symbol,"capability":cap,"state":None,"lineage":None,"frozen":None,
             "reason_codes":[],"direction_sample_count":0,"producer_output_digest":digest(card.get("prediction_snapshot_v2") or card.get("prediction") or {})}
        if cap == "CAPABILITY_UNAVAILABLE":
            r.update(direction_status="NOT_APPLICABLE", reason_codes=["NO_SESSION_DIRECTION_PRODUCER"])
            r["producer_evidence"] = deepcopy(card.get("prediction") or {})
        elif source is None:
            r.update(state="HISTORICAL_INELIGIBLE" if cap=="NATIVE_DIRECTION" else None,
                     reason_codes=["NO_CONTEMPORANEOUS_FROZEN_EVIDENCE"])
        elif not isinstance(source,dict) or source.get("status") != "FROZEN":
            r.update(state="BLOCKED_INPUT",reason_codes=["NATIVE_FROZEN_PREREQUISITE"])
        else:
            try:
                f = source["frozen"]
                validate_frozen(f)
                if f["symbol"] != symbol or f["prediction_id"] != (card.get("prediction_snapshot_v2") or {}).get("prediction_identity"):
                    raise ValueError("ORIGIN_IDENTITY")
                r.update(lineage=lineage(f),frozen=deepcopy(f))
                if cap == "NATIVE_DIRECTION":
                    r.update(state="WAITING_OUTCOME",direction_sample_count=1)
            except (ValueError,KeyError,TypeError):
                r.update(state="BLOCKED_INPUT",reason_codes=["FROZEN_INTEGRITY"])
        records.append(r)
    return stamp({"schema_version":VERSION,"kind":"REPORT_EVIDENCE","report_identity":{k:snapshot[k] for k in
                  ("snapshot_id","revision","market","window","effective_trading_date","run_kind")},
                  "report_digest":digest(snapshot),"records":records,"comparison":{"status":"NO_PREDECESSOR"},
                  "input_kind":"PRODUCTION_DERIVED","lifecycle_mutation":False})

def persist(snapshot_path):
    path = Path(snapshot_path)
    if path.is_symlink() or path.stat().st_size > 32*1024*1024:
        raise ValueError("SOURCE_PATH")
    snapshot=json.loads(path.read_text())
    if tuple(path.parts[-4:-1]) != (snapshot["market"].lower(),snapshot["window"],snapshot["effective_trading_date"]):
        raise ValueError("SOURCE_PATH_IDENTITY")
    sources={}
    if snapshot["market"]=="TW":
        root=path.parents[3]
        day=snapshot["effective_trading_date"]
        for f in (root/"tw/pre_open_0700"/day/".frozen").glob("*.json"):
            if f.is_symlink() or f.stat().st_size>1024*1024:
                raise ValueError("FROZEN_PATH")
            v=json.loads(f.read_text())
            verify(v)
            key=v["native_prediction_id"]
            previous=sources.get(key)
            if previous is None or (v.get("capture_phase")=="RESULT" and previous.get("capture_phase")!="RESULT"):
                sources[key]=v
            elif v.get("capture_phase")==previous.get("capture_phase") and v!=previous:
                raise ValueError("FROZEN_RECEIPT_CONFLICT")
    value=project(snapshot,sources)
    target=path.parent/".evidence"/(value["content_hash"]+".json")
    publish(target,value)
    reevaluate(path,value)
    return {"status":"EVIDENCE_ACCUMULATED","content_hash":value["content_hash"],"path":str(target)}


def reevaluate(snapshot_path, current, *, data_root=None, observed_at=None):
    """Bounded replay of scheduled, admitted native evidence; no historical inference."""
    import csv
    import io
    import hashlib
    from datetime import datetime, timezone
    from app.evaluation.production_evidence import outcome, evaluate_direction, unique_predictions
    from app.evaluation.prediction_regression_contract import aware
    path=Path(snapshot_path)
    if current["report_identity"]["market"]!="TW" or current["report_identity"]["run_kind"]!="scheduled":
        return []
    archive=path.parents[3]
    root=Path(data_root) if data_root else Path(__file__).resolve().parents[2]
    day=current["report_identity"]["effective_trading_date"]
    candidates={}
    report_bindings={}
    # Ten required sessions plus bounded headroom; never read raw report history.
    dirs=sorted((archive/"tw/pre_open_0700").glob("????-??-??"),reverse=True)
    for d in [d for d in dirs if d.name<=day][:12]:
        for p in sorted((d/".evidence").glob("*.json"))[:16]:
            if p.is_symlink() or p.stat().st_size>8*1024*1024:
                raise ValueError("EVIDENCE_PATH")
            record=json.loads(p.read_text());verify(record)
            if record["report_identity"]["run_kind"]!="scheduled":
                continue
            for r in record["records"]:
                if r["capability"]=="NATIVE_DIRECTION" and r["frozen"] is not None:
                    f=r["frozen"];validate_frozen(f)
                    candidates.setdefault(f["symbol"],[]).append(f)
                    report_bindings.setdefault(f["sample_id"],record["report_identity"])
    results=[]
    for symbol,entries in sorted(candidates.items()):
        if not symbol.isdigit() or len(symbol)>8:
            raise ValueError("SYMBOL")
        predictions=unique_predictions(entries)
        source=root/"data/historical"/(symbol+"_daily.csv")
        outcomes={}
        observed_at=observed_at or datetime.now(timezone.utc).isoformat()
        if source.exists():
            if source.is_symlink() or source.stat().st_size>4*1024*1024:
                raise ValueError("SOURCE_PATH")
            raw=source.read_bytes();sha=hashlib.sha256(raw).hexdigest()
            rows=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
            for f in predictions:
                h=f["event"]["horizon"]
                if aware(observed_at)<aware(h["close_at"]):
                    continue
                matching=[r for r in rows if r.get("date")==h["session_date"]]
                if len(matching)!=1 or not any(r.get("date","") > h["session_date"] for r in rows):
                    continue
                # A daily bar persisted before its close cannot prove finality.
                if source.stat().st_mtime < aware(h["close_at"]).timestamp():
                    continue
                key=digest({"sample":f["sample_id"],"source":sha,"version":VERSION})
                target=archive/"tw/pre_open_0700"/h["session_date"]/".outcome"/(key+".json")
                if target.exists():
                    value=json.loads(target.read_text());verify(value)
                else:
                    value=outcome(f,close=float(matching[0]["close"]),source="canonical_historical_csv",
                                  revision=sha,source_digest=sha,available_at=observed_at,session_date=h["session_date"],report_identity=report_bindings[f["sample_id"]])
                    publish(target,value)
                outcomes[f["sample_id"]]=value
        # Semantic cutoff is explicitly captured; replay never consults wall clock.
        calendar=predictions[0]["calendar"]
        completed=[r["session_date"] for r in calendar["days"] if r["state"] in {"NORMAL","EARLY_CLOSE"}
                   and r["session_date"]<=day and aware(r["close_at"])<=aware(observed_at)]
        if not completed:
            continue
        review=completed[-1]
        # Stabilize evaluation identity across retries of unchanged admitted inputs.
        identity=digest({"predictions":[f["content_hash"] for f in predictions],
                         "outcomes":{k:v["content_hash"] for k,v in outcomes.items()},
                         "session":review,"contract":VERSION,"symbol":symbol})
        target=path.parent/".assessment"/(identity+".json")
        if target.exists():
            saved=json.loads(target.read_text());verify(saved)
            replay=evaluate_direction(saved["predictions"],saved["outcomes"],calendar=saved["calendar"],
                                      review_session=saved["review_session"],observed_at=saved["observed_at"])
            if saved["result"]!=replay:
                raise ValueError("ASSESSMENT_REPLAY")
        else:
            result=evaluate_direction(predictions,outcomes,calendar=calendar,review_session=review,observed_at=observed_at)
            saved=stamp({"schema_version":VERSION,"kind":"DIRECTION_ASSESSMENT","identity":identity,
                         "symbol":symbol,"market":"TW","stream":current["report_identity"]["window"],"prediction_stream":"pre_open_0700","run_kind":"scheduled",
                         "predictions":predictions,"outcomes":outcomes,"calendar":calendar,"review_session":review,
                         "observed_at":observed_at,"result":result,"comparison":{"status":"NO_PREDECESSOR"},
                         "report_bindings":report_bindings,"finding_fix_evidence":[],"lifecycle_mutation":False})
            prior=None
            for directory in sorted(path.parent.parent.glob("????-??-??"),reverse=True):
                if directory.name>=review:
                    continue
                for candidate in sorted((directory/".assessment").glob("*.json"),reverse=True)[:16]:
                    if candidate.is_symlink() or candidate.stat().st_size>8*1024*1024:
                        continue
                    try:
                        item=json.loads(candidate.read_text())
                        if item.get("symbol")==symbol and item.get("result",{}).get("state")=="EVALUATED":
                            prior=item
                            break
                    except (OSError,ValueError):
                        prior={"invalid":True}
                        break
                if prior is not None:
                    break
            saved=bind_assessment(saved,prior)
            publish(target,saved)
        results.append({"identity":identity,"state":saved["result"]["state"]})
    return results


def bind_assessment(current, predecessor=None):
    from app.evaluation.production_evidence import evaluate_direction
    from app.evaluation.offline_report_projection import evidence_chain
    value=deepcopy(current)
    value["evidence_chain"]=evidence_chain({"evidence_records":[],"linkage_refs":{"finding":None,"fix":None,"evaluation":None}})
    value["realized_fix_effect"]="INSUFFICIENT_EVIDENCE"
    value["comparison"]={"status":"NO_PREDECESSOR"}
    if predecessor is not None:
        try:
            verify(predecessor)
            if predecessor["result"]["state"]!="EVALUATED" or predecessor["run_kind"]!="scheduled" or current["run_kind"]!="scheduled":
                raise ValueError("PREDECESSOR_ELIGIBILITY")
            if any(current[k]!=predecessor[k] for k in ("market","stream","symbol","schema_version")) or predecessor["review_session"]>=current["review_session"]:
                raise ValueError("PREDECESSOR_IDENTITY")
            replay=evaluate_direction(predecessor["predictions"],predecessor["outcomes"],calendar=predecessor["calendar"],
                                      review_session=predecessor["review_session"],observed_at=predecessor["observed_at"])
            if replay!=predecessor["result"]:
                raise ValueError("PREDECESSOR_REPLAY")
            value["comparison"]={"status":"BOUND" if current["result"]["state"]=="EVALUATED" else "INSUFFICIENT_COMPARISON",
                                 "predecessor_identity":predecessor["identity"],"predecessor_hash":predecessor["content_hash"],
                                 "predecessor_schema":predecessor["schema_version"],"current_identity":current["identity"],
                                 "relationship":"PRIOR_SCORED_SESSION_SAME_STREAM","component_evidence":deepcopy(predecessor["result"])}
        except (ValueError,KeyError,TypeError):
            value["comparison"]={"status":"REJECTED","reason":"PREDECESSOR_INTEGRITY"}
    return stamp(value)

