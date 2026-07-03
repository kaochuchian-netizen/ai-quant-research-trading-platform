from __future__ import annotations
from collections import Counter,defaultdict
from typing import Any
WINDOWS=["pre_open_0700","intraday_1305","pre_close_1335","post_close_1500","prediction_review_1500"]
TYPES=["approved_delivery","prediction_snapshot","actual_outcome","evaluation","confidence_calibration","factor_recommendation","dashboard_intelligence"]
def build_completeness_summary(records:list[dict[str,Any]])->dict[str,Any]:
    by_window={w:{"records_found":0,"missing":True,"finding":"missing"} for w in WINDOWS}
    for r in records:
        w=r.get("scheduler_window")
        if w in by_window:
            by_window[w]["records_found"]+=1; by_window[w]["missing"]=False
    for v in by_window.values():
        if v["records_found"]>=5: v["finding"]="complete"
        elif v["records_found"]>0: v["finding"]="partial"
    by_type=Counter(r.get("artifact_type","unknown") for r in records)
    by_status=Counter(r.get("artifact_status","unknown") for r in records)
    by_stock=defaultdict(lambda:{"records_found":0,"missing_prediction_snapshot":True,"missing_actual_outcome":True,"missing_evaluation":True,"pending_outcome":0,"insufficient_data":0})
    for r in records:
        sid=r.get("stock_id") or "unknown"
        b=by_stock[sid]; b["records_found"]+=1
        if r.get("artifact_type")=="prediction_snapshot": b["missing_prediction_snapshot"]=False
        if r.get("artifact_type")=="actual_outcome": b["missing_actual_outcome"]=False
        if r.get("artifact_type")=="evaluation": b["missing_evaluation"]=False
        if r.get("artifact_status")=="pending": b["pending_outcome"]+=1
        if r.get("artifact_status")=="insufficient_data": b["insufficient_data"]+=1
    return {"total_records":len(records),"by_scheduler_window":by_window,"by_stock_id":dict(by_stock),"by_artifact_type":{"expected":TYPES,"found":dict(by_type),"missing":[t for t in TYPES if by_type.get(t,0)==0],"stale":by_status.get("stale",0),"malformed":by_status.get("malformed",0),"duplicate":by_status.get("duplicate",0)},"findings":{"overall":"partial" if records else "not_available","pending_count":by_status.get("pending",0),"insufficient_data_count":by_status.get("insufficient_data",0),"malformed_count":by_status.get("malformed",0),"duplicate_count":by_status.get("duplicate",0)}}
