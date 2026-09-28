#!/usr/bin/env python3
"""Single artifact-only 17:00 entrypoint. No transports, scheduler or market fetch."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from app.dashboard.daily_evaluation_archive import ARCHIVE, collect, persist_daily, read
from app.evaluation.daily_evaluation import build_daily, replay, canonical_cutoff
from app.evaluation.prediction_regression_contract import aware

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--report-date",help="Canonical Taipei daily identity; required for explicit reruns.")
    parser.add_argument("--readiness",action="store_true",help="Read only: resolve inputs and replay, no persistence.")
    parser.add_argument("--replay",type=Path,help="Read/replay an immutable artifact only.")
    parser.add_argument("--shadow-output",type=Path,help="Isolated output; does not enter scheduled predecessor chain.")
    args=parser.parse_args(argv)
    try:
        if args.replay:
            value=read(args.replay);replay(value)
            print(json.dumps({"status":"REPLAY_PASS","identity":value["identity"]},sort_keys=True));return 0
        now=datetime.now(ZoneInfo("Asia/Taipei"))
        day=args.report_date or now.date().isoformat()
        if aware(canonical_cutoff(day))>now and not args.readiness:
            raise ValueError("CANONICAL_CUTOFF_NOT_REACHED")
        if args.readiness:
            value=build_daily(day,collect(ARCHIVE,day));replay(value);path=None
        else:
            path,value=persist_daily(ARCHIVE,day,output_root=args.shadow_output)
        print(json.dumps({"status":value["status"],"identity":value["identity"],"path":str(path) if path else None,
                          "sessions":{m:v.get("review_session") for m,v in value["markets"].items()},
                          "notification":False,"scheduler_mutation":False},sort_keys=True))
        return 0 if value["status"]=="VALID" else 1
    except (ValueError,KeyError,TypeError,OSError):
        # Stable bounded diagnostics, no payload or exception text.
        print(json.dumps({"status":"BLOCKED_INPUT","reason":"DAILY_PREREQUISITE_OR_PERSISTENCE","notification":False},sort_keys=True))
        return 1

if __name__=="__main__":
    raise SystemExit(main())
