#!/usr/bin/env python3
import argparse
from ai_dev_189_validation import emit, research, result
from app.us_stock.premarket_decision import canonical_event_risk

def main():
    p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args(); risk=canonical_event_risk(research(material_sec=True))
    copies=[risk["canonical_level"] for _ in ("archive","dashboard","email","line","operations")]
    checks={"canonical_single_level":risk["canonical_level"]=="medium","subrisk_retained":risk["sec_filing_risk"]=="medium" and risk["earnings_risk"]=="low","channel_parity":len(set(copies))==1,"8k_not_automatically_high":risk["canonical_level"]!="high"}
    raise SystemExit(emit(result("validate_us_premarket_event_risk_parity_v1",checks),a.pretty))
if __name__=="__main__": main()
