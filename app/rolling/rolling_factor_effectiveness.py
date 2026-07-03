from __future__ import annotations
from typing import Any
def build_rolling_factor_effectiveness_readiness(records:list[dict[str,Any]], sample_mode:bool)->dict[str,Any]:
    factors=[r for r in records if r.get('artifact_type') in {'factor_recommendation','source_evidence','feature_attribution'} and r.get('artifact_status')=='valid']
    n=len(factors)
    return {"sample_mode":sample_mode,"factor_sample_size":n,"usable_factor_records":n,"factor_groups_available":sorted({r.get('artifact_type') for r in factors}),"source_groups_available":[],"recommendation_readiness":"data_collection_only" if n<20 else "research_ready","insufficient_sample_reasons":["usable factor records below 20"] if n<20 else [],"factor_effectiveness_status":"demo_only" if sample_mode else ("usable" if n>=20 else "insufficient_sample"),"production_mutation_allowed":False,"recommended_action":"collect_more_real_history" if n<20 else "offline_research_only"}
