#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from app.reports.canonical_outcomes import aggregate_outcomes
from app.reports.decision_intelligence_v4 import project_decision_intelligence_v4, compact_summary

def card(symbol,outcome): return {"symbol":symbol,"canonical_outcome":outcome,"strategies":{"daily_tactical":{"action":"觀望"}}}
def validate():
    pending=[card(f"S{i}","pending") for i in range(6)]
    all_pending=aggregate_outcomes(pending)
    mixed=[card("H1","hit"),card("H2","hit"),card("F","fail"),card("N","not_triggered"),card("T","no_trade"),card("P","pending")]
    aggregate=aggregate_outcomes(mixed)
    projection=project_decision_intelligence_v4("US","us_post_close_review_0630",{"cards":pending})
    checks={
      "all_pending_universe":all_pending["pending_count"]==6,
      "pending_not_no_trade":all_pending["no_trade_count"]==0 and projection["outcome_distribution"]=={"pending":6},
      "completed_zero":all_pending["completed_review_count"]==0,
      "mixed_total":aggregate["review_card_count"]==6 and aggregate["completed_review_count"]==5,
      "channel_summary_pending": "無交易 6" not in compact_summary(projection,"email"),
    }
    duplicate_failed=False
    try: aggregate_outcomes([card("X","pending"),card("X","no_trade")])
    except ValueError: duplicate_failed=True
    checks["duplicate_rejected"]=duplicate_failed
    return {"ok":all(checks.values()),"checks":checks,"all_pending":all_pending,"mixed":aggregate,"runtime_archive_dashboard_email_line_operations_source":"structured_review_cards"}
def main():
 p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
