from __future__ import annotations
from datetime import datetime,timezone
from collections import Counter
from typing import Any
from .completeness import build_completeness_summary
from .deduplication import deduplicate
from .schemas import STORE_SCHEMA_VERSION, HistoricalArtifactStore, safety_summary
def now()->str: return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def build_index(records:list[dict[str,Any]])->dict[str,Any]:
    return {"by_artifact_type":dict(Counter(r.get("artifact_type") for r in records)),"by_scheduler_window":dict(Counter(r.get("scheduler_window") or "unknown" for r in records)),"by_status":dict(Counter(r.get("artifact_status") for r in records)),"stock_ids":sorted({r.get("stock_id") for r in records if r.get("stock_id")})}
def build_historical_store(records:list[dict[str,Any]], store_id:str="offline-history-store") -> HistoricalArtifactStore:
    unique,dedup=deduplicate(records)
    return HistoricalArtifactStore(STORE_SCHEMA_VERSION,now(),store_id,unique,build_index(unique),build_completeness_summary(unique),dedup,safety_summary())
