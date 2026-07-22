#!/usr/bin/env python3
import argparse
from ai_dev_189_validation import build, context, emit, result
from app.us_stock.premarket_decision import normalize_market_context, summarize_premarket, validate_premarket_contract

def main():
    p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args()
    good=build("NVDA"); tsm=build("TSM",rr=.35,confidence=26,direction="neutral",action="等待止穩"); googl=build("GOOGL",rr=.36,confidence=34,direction="neutral",action="等待止穩")
    cards=[good,tsm,googl]; summary=summarize_premarket(cards,normalize_market_context(context()))
    checks={"valid_opportunity":good["eligibility"]["top_opportunity"] and good["eligibility"]["actionable"],"tsm_demoted":not tsm["eligibility"]["top_opportunity"] and tsm["eligibility"]["no_trade"] and tsm["trade_plan"]["status"]=="watch_only","googl_no_active_plan":googl["trade_plan"]["entry"] is None and googl["trade_plan"]["observation_zone"] is not None,"count_list_parity":summary["top_opportunity_count"]==1 and summary["groups"]["top_opportunity"]==["NVDA"],"exclusivity":not validate_premarket_contract(cards,summary)}
    raise SystemExit(emit(result("validate_us_premarket_opportunity_eligibility_v1",checks),a.pretty))
if __name__=="__main__": main()
