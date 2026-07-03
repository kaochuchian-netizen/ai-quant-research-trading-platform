from __future__ import annotations
from typing import Any
def build_rolling_calibration_readiness(records:list[dict[str,Any]], sample_mode:bool)->dict[str,Any]:
    confidence=[r for r in records if r.get('artifact_type') in {'evaluation','confidence_calibration'} and r.get('artifact_status')=='valid']
    n=len(confidence)
    return {"sample_mode":sample_mode,"calibration_sample_size":n,"usable_confidence_records":n,"bucket_readiness":"usable" if n>=20 else "insufficient_sample","weighted_ece_if_available":None,"over_confident_bucket_count":0 if n<20 else None,"under_confident_bucket_count":0 if n<20 else None,"insufficient_bucket_count":1 if n<20 else 0,"calibration_status":"demo_only" if sample_mode else ("usable" if n>=20 else "insufficient_sample")}
