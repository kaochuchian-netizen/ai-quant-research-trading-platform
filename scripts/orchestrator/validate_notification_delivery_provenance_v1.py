#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from app.reports.delivery_provenance import build_delivery_provenance
from app.dashboard.market_dashboard_alias import payload_hash
from app.reports.tw_pre_open_structured import render_email, render_line
from scripts.orchestrator.validate_tw_pre_open_0700_structured_payload_v1 import fixture_payload

def validate():
 snapshot={"snapshot_id":"s1","revision":2,"payload_hash":"h1"}
 payload=build_delivery_provenance(market="TW",window="intraday_1305",trading_date="2026-07-17",snapshot=snapshot,canonical_url="/dashboard/archive/tw/intraday_1305/latest/index.html",channel="email",content="content",delivery_result="dry_run_not_sent",delivery_attempted=False,recipient_count=0)
 required={"snapshot_id","revision","source_payload_hash","presentation_content_hash","delivery_result","recipient_count"}
 serialized=json.dumps(payload,ensure_ascii=False).lower()
 forbidden=("recipient_email","line_user_id","access_token","authorization")
 checks={"required_retained":required<=payload.keys(),"source_identity":payload["source_payload_hash"]=="h1","separate_hash":payload["presentation_content_hash"]!="h1","delivery_result":payload["delivery_result"]=="dry_run_not_sent","no_sensitive_fields":not any(x in serialized for x in forbidden)}
 tw_payload=fixture_payload(); source_hash=payload_hash(tw_payload)
 tw_snapshot={"snapshot_id":"tw0700-controlled","revision":1,"payload_hash":source_hash,"payload":tw_payload}
 canonical_url="/dashboard/archive/tw/pre_open_0700/latest/index.html"
 email=build_delivery_provenance(market="TW",window="pre_open_0700",trading_date="2099-07-17",snapshot=tw_snapshot,canonical_url=canonical_url,channel="email",content=render_email(tw_payload,canonical_url),delivery_result="dry_run_not_sent",delivery_attempted=False,recipient_count=0)
 line=build_delivery_provenance(market="TW",window="pre_open_0700",trading_date="2099-07-17",snapshot=tw_snapshot,canonical_url=canonical_url,channel="line",content=render_line(tw_payload,canonical_url),delivery_result="dry_run_not_sent",delivery_attempted=False,recipient_count=0)
 checks["tw_0700_email_source_parity"]=email["source_payload_hash"]==source_hash
 checks["tw_0700_line_source_parity"]=line["source_payload_hash"]==source_hash
 checks["tw_0700_presentation_hashes_separate"]=email["presentation_content_hash"]!=source_hash and line["presentation_content_hash"]!=source_hash
 checks["tw_0700_canonical_url"]=email["canonical_url"]==line["canonical_url"]==canonical_url
 return {"ok":all(checks.values()),"checks":checks,"payload":payload,"tw_0700":{"source_payload_hash":source_hash,"email_source_payload_hash":email["source_payload_hash"],"line_source_payload_hash":line["source_payload_hash"],"canonical_url":canonical_url},"email_attempted":False,"line_attempted":False}
def main():
 p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
