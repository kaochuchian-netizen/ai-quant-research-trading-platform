#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from app.history.artifact_normalizer import normalize_artifact
from app.history.artifact_scanner import scan_artifacts, missing_path_result
from app.history.historical_store import build_historical_store

def offline_payloads():
    return [
      {"schema_version":"approved_scheduler_delivery_v1","run_id":"approved-post_close_1500-delivery-20260703-150001","generated_at":"2026-07-03T15:00:01+08:00","scheduler_window":"post_close_1500","pipeline_type":"post_close","content_state":"prediction_review_pending","advisory_only":True,"line_delivery":{},"email_delivery":{},"dashboard_delivery":{}},
      {"schema_version":"prediction_snapshot_v1","run_id":"pred-001","generated_at":"2026-07-01T07:00:00+08:00","scheduler_window":"pre_open_0700","pipeline_type":"pre_open","stock_id":"2330","stock_name":"台積電","prediction_target":"next_day_high_low","advisory_only":True},
      {"schema_version":"actual_outcome_v1","run_id":"outcome-001","generated_at":"2026-07-02T15:00:00+08:00","stock_id":"2330","stock_name":"台積電","actual_return_1d":0.01,"advisory_only":True},
      {"schema_version":"prediction_evaluation_v1","run_id":"eval-001","generated_at":"2026-07-02T15:10:00+08:00","stock_id":"2330","stock_name":"台積電","prediction_target":"next_day_high_low","direction_hit":True,"actual_return_1d":0.01,"high_error_pct":0.02,"low_error_pct":0.01,"advisory_only":True},
      {"schema_version":"confidence_calibration_v1","run_id":"cal-001","generated_at":"2026-07-03T16:00:00+08:00","confidence_bucket_analysis":[],"advisory_only":True},
      {"schema_version":"factor_recommendation_v1","run_id":"factor-001","generated_at":"2026-07-03T16:10:00+08:00","factor_effectiveness":[],"production_mutation_allowed":False,"advisory_only":True},
      {"schema_version":"dashboard_intelligence_v1","run_id":"dash-001","generated_at":"2026-07-03T16:20:00+08:00","stock_intelligence_cards":[],"production_publish_allowed":False,"advisory_only":True},
      "incident diagnostic: pre_open_0700_hung process captured",
      {"schema_version":"prediction_evaluation_v1","run_id":"eval-pending","generated_at":"2026-07-03T15:10:00+08:00","stock_id":"2317","content_state":"pending","advisory_only":True},
      {"schema_version":"prediction_evaluation_v1","run_id":"eval-insufficient","generated_at":"2026-07-03T15:20:00+08:00","stock_id":"2454","content_state":"insufficient_data","advisory_only":True},
    ]
def build_store_from_payloads(payloads, source_kind='offline_sample'):
    records=[normalize_artifact(p,source_path=f"offline://sample/{i}",source_kind=source_kind).to_dict() for i,p in enumerate(payloads)]
    records.append(records[0].copy())
    return build_historical_store(records).to_dict()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--pretty',action='store_true'); ap.add_argument('--input'); ap.add_argument('--output'); ap.add_argument('--scan-path',action='append',default=[]); ap.add_argument('--offline-sample',action='store_true'); ap.add_argument('--dry-run',action='store_true',default=True); ap.add_argument('--include-runtime',action='store_true')
    a=ap.parse_args()
    if a.input:
        data=json.loads(Path(a.input).read_text(encoding='utf-8')); payloads=data.get('artifacts',data if isinstance(data,list) else [data]); store=build_store_from_payloads(payloads,'input_file')
    elif a.scan_path:
        scan=scan_artifacts(a.scan_path,'real_runtime' if a.include_runtime else 'scan_path'); store=build_historical_store(scan['records'],'scan-history-store').to_dict(); store['scan_result']={k:v for k,v in scan.items() if k!='records'}
    else:
        store=build_store_from_payloads(offline_payloads(),'offline_sample'); store['sample_mode']=True
    text=json.dumps(store,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True)
    if a.output:
        out=Path(a.output)
        if str(out).startswith('/var/www/stock-ai-dashboard'): raise SystemExit('refusing to write dashboard production path')
        out.parent.mkdir(parents=True,exist_ok=True); out.write_text(text+'\n',encoding='utf-8')
    else: sys.stdout.write(text+'\n')
    return 0
if __name__=='__main__': raise SystemExit(main())
