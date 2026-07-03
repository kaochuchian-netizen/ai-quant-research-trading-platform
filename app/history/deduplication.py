from __future__ import annotations
import hashlib,json
from typing import Any
def stable_fingerprint(payload: Any)->str:
    text=json.dumps(payload,ensure_ascii=False,sort_keys=True,default=str) if not isinstance(payload,str) else payload
    return hashlib.sha256(text.encode()).hexdigest()[:24]
def make_dedupe_key(record: dict[str,Any])->str:
    parts=[record.get(k) or "" for k in ["run_id","scheduler_window","pipeline_type","stock_id","prediction_target","artifact_type","generated_at","run_date","run_time"]]
    parts.append(record.get("fingerprint") or "")
    return "|".join(map(str,parts))
def deduplicate(records:list[dict[str,Any]])->tuple[list[dict[str,Any]],dict[str,Any]]:
    seen={}; kept=[]; dup=[]
    for r in records:
        k=r.get("dedupe_key") or make_dedupe_key(r)
        if k in seen:
            nr=dict(r); nr["artifact_status"]="duplicate"; dup.append(nr)
        else:
            seen[k]=True; kept.append(r)
    return kept,{"input_count":len(records),"unique_count":len(kept),"duplicate_count":len(dup),"duplicate_records":[d.get("record_id") for d in dup]}
