from __future__ import annotations
from typing import Any
def _nums(records, key):
    vals=[]
    for r in records:
        v=(r.get('summary') or {}).get(key)
        if isinstance(v,(int,float)) and not isinstance(v,bool): vals.append(float(v))
    return vals
def _mean(vals): return sum(vals)/len(vals) if vals else None
def build_rolling_evaluation(records:list[dict[str,Any]], sample_mode:bool)->dict[str,Any]:
    evals=[r for r in records if r.get('artifact_type')=='evaluation' and r.get('artifact_status')=='valid']
    hits=[(r.get('summary') or {}).get('direction_hit') for r in evals]
    usable_hits=[h for h in hits if isinstance(h,bool)]
    status='ready' if len(evals)>=20 else 'partial' if len(evals)>=5 else 'insufficient' if records else 'not_available'
    return {"status":status,"sample_mode":sample_mode,"sample_size":len(evals),"direction_hit_rate":_mean([1.0 if h else 0.0 for h in usable_hits]),"close_direction_hit_rate":None,"avg_return_1d":_mean(_nums(evals,'actual_return_1d')),"avg_return_5d":_mean(_nums(evals,'actual_return_5d')),"avg_return_20d":_mean(_nums(evals,'actual_return_20d')),"high_error_pct":_mean(_nums(evals,'high_error_pct')),"low_error_pct":_mean(_nums(evals,'low_error_pct')),"rating_effectiveness_summary":"insufficient_sample" if len(evals)<20 else "usable","action_effectiveness_summary":"insufficient_sample" if len(evals)<20 else "usable","pending_outcome_count":sum(1 for r in records if r.get('artifact_status')=='pending'),"missing_outcome_count":sum(1 for r in records if r.get('artifact_status')=='missing'),"insufficient_data_count":sum(1 for r in records if r.get('artifact_status')=='insufficient_data')}
