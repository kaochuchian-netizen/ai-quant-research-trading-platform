from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any
SCHEMA_VERSION="historical_artifact_record_v1"
STORE_SCHEMA_VERSION="historical_artifact_store_v1"
ARTIFACT_TYPES={"approved_delivery","prediction_snapshot","actual_outcome","evaluation","source_coverage","source_evidence","feature_attribution","stock_explanation","confidence_calibration","factor_recommendation","dashboard_intelligence","incident_diagnostic","content_quality_diagnostic","unknown"}
STATUSES={"valid","partial","pending","missing","malformed","stale","duplicate","unsupported","insufficient_data"}
@dataclass(frozen=True)
class HistoricalArtifactRecord:
    schema_version:str; record_id:str; artifact_id:str; artifact_type:str; source_path:str|None; source_kind:str; run_id:str|None; run_date:str|None; run_time:str|None; generated_at:str|None; scheduler_window:str|None; pipeline_type:str|None; stock_id:str|None; stock_name:str|None; prediction_target:str|None; content_state:str|None; artifact_status:str; ingested_at:str; fingerprint:str; dedupe_key:str; lineage:dict[str,Any]=field(default_factory=dict); summary:dict[str,Any]=field(default_factory=dict); diagnostics:dict[str,Any]=field(default_factory=dict); advisory_only:bool=True
    def to_dict(self)->dict[str,Any]: return asdict(self)
@dataclass(frozen=True)
class HistoricalArtifactStore:
    schema_version:str; generated_at:str; store_id:str; records:list[dict[str,Any]]; index:dict[str,Any]; completeness_summary:dict[str,Any]; deduplication_summary:dict[str,Any]; safety_summary:dict[str,Any]
    def to_dict(self)->dict[str,Any]: return asdict(self)
def safety_summary()->dict[str,bool]:
    return {"advisory_only":True,"production_publish_allowed":False,"production_mutation_allowed":False,"broker_login":False,"simulation_order":False,"production_order":False,"line_send":False,"email_send":False,"dashboard_production_publish":False,"line_sent":False,"email_sent":False,"dashboard_published":False,"var_www_dashboard_write":False,"scheduler_time_change":False,"cron_systemd_timer_mutation":False,"production_db_write":False,"secrets_read":False,"production_pipeline_run":False,"python3_main_py":False,"trading_execution":False,"backtesting_runtime_execution":False}
