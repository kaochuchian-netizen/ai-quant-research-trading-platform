#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from app.reports.tw_four_window_decision import sanitize_text
from scripts.orchestrator.tw_four_window_validation_fixture import payloads
ALLOWED={"official_disclosure","exchange_or_regulator","company_ir","major_financial_media","general_media","social_or_unverified"}
def validate():
 cards=payloads()["pre_open_0700"]["structured_pre_open_cards"]
 checks={"provider_error_sanitized":cards[0]["news_summary"]=="新聞分析暫時無法取得","raw_error_sanitizer":sanitize_text({"error":"504 DEADLINE_EXCEEDED"})=="新聞分析暫時無法取得","low_quality_not_promoted":cards[0]["entry_readiness"]!="entry_ready" or cards[0]["data_status"]=="partial","source_taxonomy":len(ALLOWED)==6,"summary_bounded":all(len(str(c.get("news_summary")))<=480 for c in cards)}
 return {"ok":all(checks.values()),"checks":checks,"allowed_source_classes":sorted(ALLOWED)}
def main():
 p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
