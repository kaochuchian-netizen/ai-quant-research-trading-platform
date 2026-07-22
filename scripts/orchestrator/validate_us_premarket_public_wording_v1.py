#!/usr/bin/env python3
import argparse
from ai_dev_189_validation import build, emit, result
from app.dashboard.multi_market_dashboard import _us_window_card

def main():
    p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args(); html=_us_window_card(build("TSM",rr=.35,confidence=26,direction="neutral",action="等待止穩"),"us_pre_market_2000")
    forbidden=("research factors deterministic","computed from 251","review data pending","檢討資料待接；檢討資料待接","PREMARKET_DATA_UNAVAILABLE_OR_STALE","RR_BELOW_THRESHOLD")
    checks={"no_internal_wording":not any(x in html for x in forbidden),"localized_labels":"主要交易機會" in html,"watch_plan":all(x in html for x in ("觀察區間","觀察與重新評估","不建立")),"review_placeholder_absent":"檢討資料待接" not in html}
    raise SystemExit(emit(result("validate_us_premarket_public_wording_v1",checks),a.pretty))
if __name__=="__main__": main()
