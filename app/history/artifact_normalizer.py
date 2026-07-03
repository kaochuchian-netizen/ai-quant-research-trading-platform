from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from .artifact_classifier import classify_payload,status_for_payload
from .deduplication import stable_fingerprint,make_dedupe_key
from .schemas import SCHEMA_VERSION, HistoricalArtifactRecord
def _now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def _date_time(generated_at:str|None)->tuple[str|None,str|None]:
    if not generated_at: return None,None
    return generated_at[:10], generated_at[11:19] if len(generated_at)>=19 else None
def normalize_artifact(payload:Any, source_path:str|None=None, source_kind:str="offline_sample", malformed:bool=False)->HistoricalArtifactRecord:
    artifact_type="unknown" if malformed else classify_payload(payload,source_path)
    status="malformed" if malformed else status_for_payload(payload,artifact_type)
    data=payload if isinstance(payload,dict) else {}
    gen=data.get("generated_at") or data.get("prediction_date") or data.get("target_date")
    rd,rt=_date_time(str(gen) if gen else None)
    fp=stable_fingerprint(payload)
    rid=f"hist-{artifact_type}-{fp[:12]}"
    record={"schema_version":SCHEMA_VERSION,"record_id":rid,"artifact_id":str(data.get("artifact_id") or data.get("run_id") or rid),"artifact_type":artifact_type,"source_path":source_path,"source_kind":source_kind,"run_id":data.get("run_id"),"run_date":data.get("run_date") or rd,"run_time":data.get("run_time") or rt,"generated_at":gen,"scheduler_window":data.get("scheduler_window"),"pipeline_type":data.get("pipeline_type"),"stock_id":data.get("stock_id"),"stock_name":data.get("stock_name"),"prediction_target":data.get("prediction_target"),"content_state":data.get("content_state"),"artifact_status":status,"ingested_at":_now(),"fingerprint":fp,"dedupe_key":"","lineage":{"source_path":source_path,"source_kind":source_kind},"summary":dict({"keys":sorted(data.keys())[:30] if isinstance(data,dict) else [],"sample_mode":source_kind=="offline_sample"}, **{k:data.get(k) for k in ["direction_hit","close_direction_hit","actual_return_1d","actual_return_5d","actual_return_20d","high_error_pct","low_error_pct"] if isinstance(data,dict) and k in data}),"diagnostics":{},"advisory_only":bool(data.get("advisory_only",True)) if isinstance(data,dict) else True}
    record["dedupe_key"]=make_dedupe_key(record)
    return HistoricalArtifactRecord(**record)
