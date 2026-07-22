#!/usr/bin/env python3
import argparse
from pathlib import Path
from ai_dev_189_validation import build, context, emit, result
from app.us_stock.premarket_decision import normalize_market_context, summarize_premarket
from app.reports.canonical_outcomes import CANONICAL_OUTCOMES
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS

def main():
    p=argparse.ArgumentParser(); p.add_argument("--pretty",action="store_true"); a=p.parse_args(); root=Path(__file__).resolve().parents[2]
    summary=summarize_premarket([build()],normalize_market_context(context()))
    checks={"seven_windows":sum(len(v) for v in MARKET_WINDOWS.values())==7,"fourteen_routes":sum(len(v)*2 for v in MARKET_WINDOWS.values())==14,"us23_contract":(root/"app/us_stock/intraday_observed.py").exists(),"us0630_outcomes":set(("hit","fail","not_triggered","no_trade","pending")).issubset(set(CANONICAL_OUTCOMES)),"us20_summary":summary["top_opportunity_count"]==len(summary["groups"]["top_opportunity"]),"tw_contract":(root/"app/reports/tw_four_window_decision.py").exists()}
    raise SystemExit(emit(result("validate_seven_window_post_ai_dev_189_regression_v1",checks),a.pretty))
if __name__=="__main__": main()
