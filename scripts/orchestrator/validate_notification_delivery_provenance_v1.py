#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from app.reports.delivery_provenance import build_delivery_provenance

def validate():
 snapshot={"snapshot_id":"s1","revision":2,"payload_hash":"h1"}
 payload=build_delivery_provenance(market="TW",window="intraday_1305",trading_date="2026-07-17",snapshot=snapshot,canonical_url="/dashboard/archive/tw/intraday_1305/latest/index.html",channel="email",content="content",delivery_result="dry_run_not_sent",delivery_attempted=False,recipient_count=0)
 required={"snapshot_id","revision","source_payload_hash","presentation_content_hash","delivery_result","recipient_count"}
 serialized=json.dumps(payload,ensure_ascii=False).lower()
 forbidden=("recipient_email","line_user_id","access_token","authorization")
 checks={"required_retained":required<=payload.keys(),"source_identity":payload["source_payload_hash"]=="h1","separate_hash":payload["presentation_content_hash"]!="h1","delivery_result":payload["delivery_result"]=="dry_run_not_sent","no_sensitive_fields":not any(x in serialized for x in forbidden)}
 return {"ok":all(checks.values()),"checks":checks,"payload":payload,"email_attempted":False,"line_attempted":False}
def main():
 p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
