#!/usr/bin/env python3
import argparse
from ai_dev_189_validation import REFERENCE, context, emit, quote, result
from app.us_stock.premarket_decision import normalize_market_context, normalize_premarket_quote

def main():
    p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args()
    observed=normalize_premarket_quote(quote(),REFERENCE); market=normalize_market_context(context(),REFERENCE)
    unavailable=normalize_premarket_quote(quote(None),REFERENCE)
    checks={"previous_close":observed["previous_close"]==203.2,"premarket_price":observed["price"]==205.4,"gap_deterministic":observed["gap_pct"]==round((205.4-203.2)/203.2*100,4),"timestamp_source_freshness":observed["availability"]=="available" and bool(observed["timestamp"]) and bool(observed["source"]),"spy_qqq_sector":all(market[k]["availability"]=="available" for k in ("spy","qqq","sector_proxy")),"unavailable_no_fallback":unavailable["price"] is None and unavailable["gap_pct"] is None and unavailable["availability"]=="unavailable"}
    raise SystemExit(emit(result("validate_us_premarket_data_contract_v1",checks),a.pretty))
if __name__=="__main__": main()
