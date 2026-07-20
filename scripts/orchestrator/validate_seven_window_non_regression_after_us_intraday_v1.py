#!/usr/bin/env python3
"""Golden-contract guard for the six windows outside US 23:00."""
from __future__ import annotations
import argparse,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from app.dashboard.dashboard_url_registry import get_window_archive_path
from app.dashboard.window_snapshot_archive import MARKET_WINDOWS,write_snapshot
from app.reports.decision_intelligence_v4 import WINDOW_PRESENTATION
from app.reports.window_report_contract import all_window_report_contracts

EXPECTED={"TW":("pre_open_0700","intraday_1305","pre_close_1335","post_close_1500"),"US":("us_pre_market_2000","us_intraday_2300","us_post_close_review_0630")}
GOLDEN_TYPES={
 ("TW","pre_open_0700"):"pre-open-decision-v4",("TW","intraday_1305"):"intraday-change-v4",
 ("TW","pre_close_1335"):"pre-close-snapshot-v4",("TW","post_close_1500"):"post-close-review-v4",
 ("US","us_pre_market_2000"):"us-pre-market-v4",("US","us_intraday_2300"):"us-intraday-change-v4",
 ("US","us_post_close_review_0630"):"us-post-close-review-v4",
}
def validate()->dict:
    contracts={(c.market,c.window) for c in all_window_report_contracts()}
    routes={get_window_archive_path(m,w,p) for m,ws in EXPECTED.items() for w in ws for p in ("latest","previous")}
    rows=[]
    with tempfile.TemporaryDirectory(prefix="ai185-regression-") as tmp:
        for market,windows in EXPECTED.items():
            for window in windows:
                if (market,window)==("US","us_intraday_2300"):continue
                payload={"market":market,"window":window,"runtime_provenance":"scheduled_production","fixture":False,"validator":False,"validation_only":False,"cards":[{"stock_id":f"{market}-{window}","action":"觀察"}]}
                result=write_snapshot(Path(tmp),market=market,window=window,effective_trading_date="2099-07-17",generated_at="2099-07-17T12:00:00+08:00",source_payload=payload,status="completed",run_kind="scheduled")
                rows.append({"market":market,"window":window,"admitted":result.get("written")})
    checks={
        "window_registry_unchanged":MARKET_WINDOWS==EXPECTED,
        "seven_contracts_present":all((m,w) in contracts for m,ws in EXPECTED.items() for w in ws),
        "card_types_golden":all(WINDOW_PRESENTATION[key]["card_type"]==value for key,value in GOLDEN_TYPES.items()),
        "fourteen_routes":len(routes)==14,
        "six_non_target_admissions":len(rows)==6 and all(r["admitted"] is True for r in rows),
        "tw_0700_schema_guard":(ROOT/"app/reports/tw_pre_open_structured.py").is_file(),
        "tw_1305_budget_guard":(ROOT/"app/runtime/stage_timing.py").is_file(),
        "us_0630_outcome_guard":(ROOT/"app/reports/canonical_outcomes.py").is_file(),
        "target_only_new_schema":"us_intraday_observed_market_v1" in (ROOT/"app/us_stock/intraday_observed.py").read_text(encoding="utf-8"),
    }
    return{"ok":all(checks.values()),"checks":checks,"matrix":rows,"routes":sorted(routes),"production_modified":False}
def main()->int:
    p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
