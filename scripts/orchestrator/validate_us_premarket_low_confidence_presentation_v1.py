#!/usr/bin/env python3
import argparse
from ai_dev_189_validation import build, emit, result

def main():
    p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args(); card=build("TSM",rr=.35,confidence=26,direction="neutral",action="等待止穩")
    plan=card["trade_plan"]; eligibility=card["eligibility"]
    checks={"conditional_mode":card["confidence_policy"]["presentation_mode"]=="conditional","not_actionable":not eligibility["actionable"] and not eligibility["top_opportunity"],"no_formal_levels":plan["entry"] is None and plan["stop"] is None and plan["target"] is None,"observation_zone_retained":plan["observation_zone"] is not None,"reason_codes":set(("LOW_CONFIDENCE","RR_BELOW_THRESHOLD","SETUP_NOT_STABILIZED")).issubset(eligibility["reason_codes"])}
    raise SystemExit(emit(result("validate_us_premarket_low_confidence_presentation_v1",checks),a.pretty))
if __name__=="__main__": main()
