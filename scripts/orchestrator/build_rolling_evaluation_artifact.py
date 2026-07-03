#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app.history.historical_store import build_historical_store
from app.history.schemas import safety_summary
from app.rolling.rolling_windows import build_rolling_windows
from app.rolling.rolling_evaluation import build_rolling_evaluation
from app.rolling.rolling_calibration import build_rolling_calibration_readiness
from app.rolling.rolling_factor_effectiveness import build_rolling_factor_effectiveness_readiness
from app.rolling.rolling_dashboard_summary import build_dashboard_ready_summary

def load_store(path=None):
    if path: return json.loads(Path(path).read_text(encoding='utf-8'))
    proc=subprocess.run([sys.executable,'scripts/orchestrator/ingest_real_historical_artifacts.py'],cwd=str(ROOT),text=True,stdout=subprocess.PIPE,check=False)
    return json.loads(proc.stdout)
def build_artifact(store):
    records=store.get('records',[]); sample_mode=bool(store.get('sample_mode') or any((r.get('summary') or {}).get('sample_mode') for r in records))
    windows=build_rolling_windows(records); evaluation=build_rolling_evaluation(records,sample_mode); calibration=build_rolling_calibration_readiness(records,sample_mode); factor=build_rolling_factor_effectiveness_readiness(records,sample_mode); dash=build_dashboard_ready_summary(store,windows,evaluation,calibration,factor,sample_mode)
    return {"schema_version":"rolling_evaluation_artifact_v1","generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat(),"input_summary":{"sample_mode":sample_mode,"record_count":len(records)},"historical_store_summary":{"store_id":store.get('store_id'),"record_count":len(records),"index":store.get('index')},"completeness_summary":store.get('completeness_summary'),"rolling_windows":windows,"rolling_evaluation":evaluation,"rolling_calibration_readiness":calibration,"rolling_factor_effectiveness_readiness":factor,"dashboard_ready_summary":dash,"diagnostics":{"insufficient_real_history":sample_mode or evaluation.get('status')!='ready',"no_production_mutation":True},"safety_summary":safety_summary(),"future_integration":{"controlled_retention_activation":"AI-DEV-130","backtesting_py_strategy_research":"future offline only"}}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pretty',action='store_true'); ap.add_argument('--input'); ap.add_argument('--history-store'); ap.add_argument('--output'); ap.add_argument('--offline-sample',action='store_true')
    a=ap.parse_args(); store=load_store(a.history_store or a.input); artifact=build_artifact(store); text=json.dumps(artifact,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True)
    if a.output:
        out=Path(a.output)
        if str(out).startswith('/var/www/stock-ai-dashboard'): raise SystemExit('refusing dashboard production path')
        out.parent.mkdir(parents=True,exist_ok=True); out.write_text(text+'\n',encoding='utf-8')
    else: sys.stdout.write(text+'\n')
    return 0
if __name__=='__main__': raise SystemExit(main())
