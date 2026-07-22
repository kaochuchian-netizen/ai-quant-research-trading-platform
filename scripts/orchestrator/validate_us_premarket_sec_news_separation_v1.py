#!/usr/bin/env python3
import argparse
from ai_dev_189_validation import emit, research, result
from app.us_stock.premarket_decision import separate_sec_news

def main():
    p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args(); r=research(news=False,material_sec=True); sec,news=separate_sec_news(r,[])
    checks={"sec_available":sec["availability"]=="available" and sec["form"]=="8-K","news_unavailable":news["availability"]=="unavailable" and news["headline"] is None and news["publisher"] is None,"not_copied":news["headline"]!=sec["summary"],"no_fake_news_direction":news["direction"]=="unavailable"}
    raise SystemExit(emit(result("validate_us_premarket_sec_news_separation_v1",checks),a.pretty))
if __name__=="__main__": main()
