#!/usr/bin/env python3
import argparse
from ai_dev_189_validation import build, context, emit, result
from app.us_stock.premarket_decision import normalize_market_context, summarize_premarket
from app.dashboard.multi_market_dashboard import render_us_window_report
from app.runtime.operations_provenance import build_operations_provenance
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, line_text

def main():
    p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args()
    cards=[build("NVDA"),build("TSM",rr=.35,confidence=26,direction="neutral",action="等待止穩"),build("GOOGL",rr=.36,confidence=34,direction="neutral",action="等待止穩")]
    summary=summarize_premarket(cards,normalize_market_context(context()))
    artifact={"market":"US","window":"us_pre_market_2000","generated_at":"2026-07-22T20:00:00+08:00","tracking_stock_count":3,"dashboard_ready_contract":{"cards":cards},"premarket_summary":summary,"premarket_contract":{"valid":True},"runtime_watchlist_validation":{"enabled_stock_count":3}}
    email=build_email_body(artifact,"us_pre_market_2000"); line=line_text(artifact,"us_pre_market_2000"); dashboard=render_us_window_report("us_pre_market_2000",[artifact])
    snapshot={"snapshot_id":"fixture-snapshot","effective_trading_date":"2026-07-22","revision":1,"payload":artifact}
    operations=build_operations_provenance(market="US",window="us_pre_market_2000",runtime_status="completed",runtime_trading_date="2026-07-22",snapshot=snapshot,public_sync={"status":"verified","source_payload_hash":"fixture-hash"},email_result="not_attempted",line_result="not_attempted")
    checks={"count_parity":all("主要交易機會 1" in value for value in (email,line)) and "主要交易機會</dt><dd>1" in dashboard,"symbol_parity":all("NVDA" in value for value in (email,line,dashboard)),"no_conflicting_top":all("TSM" not in ((summary.get("groups") or {}).get("top_opportunity") or []) for _ in [0]),"operations_summary":operations["top_opportunity_count"]==1 and operations["no_trade_count"]==2,"no_delivery":operations["email_delivery_result"]=="not_attempted" and operations["line_delivery_result"]=="not_attempted"}
    raise SystemExit(emit(result("validate_us_premarket_channel_parity_v1",checks),a.pretty))
if __name__=="__main__": main()
