#!/usr/bin/env python3
"""Preview or explicitly deliver the approved immutable 2026-10-19 reissue.

Default mode is no-send and performs no artifact, dashboard, or runtime write.
``--send`` also requires ``--confirmed-reissue`` and uses the existing
content-addressed channel receipt contract.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.reports.tw_post_close_reissue import (
    REISSUE_LABEL, SNAPSHOT_ID, TRADING_DATE, WINDOW, load_bound_snapshot, prepare_reissue,
)
from scripts.orchestrator.approved_pre_open_delivery import (
    DEFAULT_MAIL_ENV_FILE, TW_POSTCLOSE_CHANNEL_RECEIPTS, send_concise_line, send_delivery_email,
)

DEFAULT_SNAPSHOT = ROOT / "artifacts/archive/window_snapshots/tw/post_close_1500/2026-10-19/revision-0001.json"
DEFAULT_DASHBOARD_URL = "http://35.201.242.167/stock-ai-dashboard/dashboard/archive/tw/post_close_1500/latest/index.html"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--dashboard-url", default=DEFAULT_DASHBOARD_URL)
    parser.add_argument("--mail-env-file", default=str(DEFAULT_MAIL_ENV_FILE))
    parser.add_argument("--receipt-root", default=str(TW_POSTCLOSE_CHANNEL_RECEIPTS))
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--confirmed-reissue", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = load_bound_snapshot(Path(args.snapshot))
    prepared = prepare_reissue(snapshot, args.dashboard_url)
    result = {
        "schema_version": "tw_post_close_snapshot_reissue_v1",
        "mode": "send" if args.send else "preview",
        "trading_date": TRADING_DATE,
        "window": WINDOW,
        "snapshot_id": SNAPSHOT_ID,
        "revision": 1,
        "reissue_label": REISSUE_LABEL,
        "line": prepared.line,
        "email": prepared.email,
        "summary": prepared.summary,
        "card_count": len(prepared.rows),
        "notification_attempted": False,
        "notification_sent": False,
        "dashboard_latest_modified": False,
        "archive_modified": False,
    }
    if args.send:
        if not args.confirmed_reissue:
            raise SystemExit("--confirmed-reissue is required with --send")
        generated_at = "2026-10-19T15:00:00+08:00"
        root = Path(args.receipt_root)
        result["email_delivery"] = send_delivery_email(
            Path(args.mail_env_file), WINDOW, "controlled-reissue-20261019", generated_at,
            "completed", args.dashboard_url, "", snapshot, root, rendered_body=prepared.email,
            subject_prefix=REISSUE_LABEL,
        )
        result["line_delivery"] = send_concise_line(
            WINDOW, generated_at, "completed", args.dashboard_url, "", snapshot, root,
            rendered_message=prepared.line,
        )
        result["notification_attempted"] = True
        result["notification_sent"] = all(
            result[channel].get("send_status") in {"sent", "already_delivered"}
            for channel in ("email_delivery", "line_delivery")
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
