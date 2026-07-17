#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,sys
from datetime import date,datetime
from pathlib import Path
from zoneinfo import ZoneInfo
REPO_ROOT=Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path: sys.path.insert(0,str(REPO_ROOT))
from app.reports.presentation_normalization import UNSAFE_FINANCIAL_TEXT,normalize_date_presentation,normalize_financial_value

def validate():
 safe=normalize_financial_value(4103900000000,unit="currency",currency="TWD",scale=1,source="deterministic",period_end=date(2026,6,30),filing_date=date(2026,7,15))
 unsafe=normalize_financial_value(4103.9,unit=None,currency="USD",scale=None,source="deterministic")
 values=[normalize_date_presentation(date(2026,7,31)),normalize_date_presentation(datetime(2026,7,31,16,0,tzinfo=ZoneInfo("America/New_York")))]
 checks={"safe_metadata":safe["safe_to_present"] and safe["raw_currency"]=="TWD" and safe["normalized_currency"]=="TWD","unsafe_not_guessed":not unsafe["safe_to_present"] and unsafe["presentation"]==UNSAFE_FINANCIAL_TEXT,"iso_date":values[0]=="2026-07-31","datetime_timezone":"-04:00" in values[1],"no_python_repr":not any("datetime." in item for item in values)}
 return {"ok":all(checks.values()),"checks":checks,"safe":safe,"unsafe":unsafe,"dates":values}
def main():
 p=argparse.ArgumentParser();p.add_argument("--pretty",action="store_true");a=p.parse_args();r=validate();print(json.dumps(r,ensure_ascii=False,indent=2 if a.pretty else None,sort_keys=True));return 0 if r["ok"] else 1
if __name__=="__main__":raise SystemExit(main())
