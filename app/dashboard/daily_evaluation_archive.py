"""254 adapter in the existing window archive; immutable reads and sidecars only."""
import json
from pathlib import Path
from app.evaluation.daily_evaluation import (VERSION, ORIGINS, canonical_cutoff, build_daily, build_market,
                                           replay, predecessor_proof)
from app.evaluation.production_evidence import verify
from app.evaluation.prediction_regression_contract import aware, stamp
from app.evaluation.session_calendar import load_calendar, latest_completed_session
from app.evaluation.offline_report_projection import digest
from app.dashboard.production_evidence_archive import publish

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE=ROOT/"artifacts/archive/window_snapshots"

def read(path,limit=32*1024*1024):
    path=Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or path.stat().st_size>limit:
        raise ValueError("ARTIFACT_PATH")
    return json.loads(path.read_text())

def files(directory,limit):
    values=sorted(Path(directory).glob("*.json"))
    if len(values)>limit:
        raise ValueError("ARTIFACT_BOUND_EXCEEDED")
    return values

def collect_market(archive,market,calendar,cutoff):
    review=latest_completed_session(calendar,market,cutoff)["session_date"]
    days=[d["session_date"] for d in calendar["days"] if d["state"] in {"NORMAL","EARLY_CLOSE"} and d["session_date"]<=review][-10:]
    records=[];outcomes=[]
    from app.dashboard.window_snapshot_archive import snapshot_id, admission_errors
    for day in days:
        directory=Path(archive)/market.lower()/ORIGINS[market]/day
        for path in files(directory/".evidence",32):
            value=read(path);verify(value)
            if path.stem!=value["content_hash"]:
                raise ValueError("EVIDENCE_PATH_IDENTITY")
            identity=value["report_identity"]
            if identity.get("run_kind")!="scheduled" or value.get("input_kind")!="PRODUCTION_DERIVED" or value.get("synthetic"):
                continue
            if (identity["market"],identity["window"],identity["effective_trading_date"])!=(market,ORIGINS[market],day):
                raise ValueError("REPORT_PATH_IDENTITY")
            source=directory/("revision-"+str(identity["revision"]).zfill(4)+".json")
            snapshot=read(source)
            if (admission_errors(snapshot) or snapshot_id({k:v for k,v in snapshot.items() if k!="snapshot_id"})!=snapshot["snapshot_id"]
                or any(snapshot[k]!=identity[k] for k in identity) or digest(snapshot)!=value["report_digest"]):
                raise ValueError("CANONICAL_REPORT_BINDING")
            if aware(snapshot["generated_at"])<=aware(cutoff):
                records.append(value)
        for p in files(directory/".outcome",128):
            item=read(p);verify(item)
            if aware(item["available_at"])<=aware(cutoff):
                outcomes.append(item)
    return {"calendar":calendar,"records":records,"outcomes":outcomes}

def collect(archive,report_date,calendars=None):
    calendars=calendars or {m:load_calendar(m) for m in ("TW","US")}
    return {m:collect_market(archive,m,calendars[m],canonical_cutoff(report_date)) for m in ("TW","US")}

def persist_daily(archive,report_date,*,output_root=None):
    archive=Path(archive)
    inputs=collect(archive,report_date)
    bare=build_daily(report_date,inputs)
    destination=Path(output_root) if output_root else archive/".daily_evaluation"
    target=destination/report_date/(bare["identity"]+".json")
    if target.exists():
        saved=read(target);replay(saved)
        if saved["identity"]!=bare["identity"]:
            raise ValueError("DAILY_IDENTITY")
        return target,saved
    # Exactly previous immutable date, deterministic ordering; same input retries
    # return the already pinned artifact above even if older archives later grow.
    previous=None
    prior_dirs=sorted((d for d in destination.glob("????-??-??") if d.name<report_date),reverse=True)
    if prior_dirs:
        candidates=files(prior_dirs[0],32)
        if candidates:
            try:
                prior=read(candidates[-1]);replay(prior)
                if prior["status"]=="VALID":
                    previous=predecessor_proof(prior)
            except (ValueError,KeyError,TypeError):
                previous={"invalid":True}
    value=build_daily(report_date,inputs,previous)
    replay(value)
    publish(target,value)
    return target,value

def post_close_review(snapshot_path):
    path=Path(snapshot_path);snapshot=read(path)
    if snapshot["market"]!="US" or snapshot["window"]!="us_post_close_review_0630" or snapshot["run_kind"]!="scheduled":
        return None
    cutoff=snapshot["generated_at"]
    calendar=load_calendar("US")
    packet=collect_market(path.parents[3],"US",calendar,cutoff)
    result=build_market("US",calendar,packet["records"],packet["outcomes"],cutoff)
    value=stamp({"schema_version":VERSION,"kind":"US_POST_CLOSE_DIRECTION_REVIEW",
                 "report_identity":{k:snapshot[k] for k in ("snapshot_id","revision","market","window","effective_trading_date","run_kind")},
                 "report_digest":digest(snapshot),"cutoff":cutoff,"inputs":packet,"result":result,
                 "legacy_range_tactical_mfe_mae":"UNCHANGED_CANONICAL_REPORT","lifecycle_mutation":False})
    target=path.parent/".review"/(value["content_hash"]+".json")
    publish(target,value)
    return target
