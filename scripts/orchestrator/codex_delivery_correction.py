#!/usr/bin/env python3
"""Isolated, no-send reevaluation of frozen delivered TW forecasts.

No transport or publisher entrypoints are imported. This is NOT a live/full
batch rerun: acquisition and 07:00 prediction generation are not executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.reports.tw_delivery_evaluation import correction
from app.reports.post_close_quality_gate import batch_gate
from app.reports.mobile_decision_presentation import render_line, render_post_close_email


def prepare(pre, post, *, session, revision, expected_pre_id, expected_post_id, dashboard_url):
    parsed = urlsplit(dashboard_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("CORRECTION_PUBLIC_URL_INVALID")
    corrected = correction(pre, post, session=session, revision=revision,
                           expected_pre_id=expected_pre_id, expected_post_id=expected_post_id)
    payload = corrected["payload"]
    gate = batch_gate(payload["structured_review_cards"], market="TW", window="post_close_1500")
    if gate["status"] != "QUALIFIED":
        raise ValueError("CORRECTION_EVIDENCE_INCOMPLETE")
    label = f"【{session[5:].replace('-', '/')} 15:00 更正報告】"
    line = label + "\n" + render_line(payload, "TW", "post_close_1500", dashboard_url, require_frozen_universe=True)
    email = label + "\n" + render_post_close_email(payload, "TW", "post_close_1500", dashboard_url)
    from app.dashboard.multi_market_dashboard import render_snapshot_archive_page
    # Explicit snapshot + previous selection avoids any mutable latest lookup.
    html = render_snapshot_archive_page("TW", "post_close_1500", "previous", corrected,
                                        {"available": False, "empty_state": "獨立更正版本，尚未正式發布"})
    receipt = {"schema_version": "tw_delivery_correction_validation_v1", "correction_id": corrected["snapshot_id"],
               "provenance": payload["correction_provenance"], "expected_symbols": payload["notification_universe"],
               "quality": gate, "line_sha256": hashlib.sha256(line.encode()).hexdigest(), "email_sha256": hashlib.sha256(email.encode()).hexdigest(),
               "html_sha256": hashlib.sha256(html.encode()).hexdigest(), "notification_sent": False, "database_write": False,
               "latest_write": False, "archive_write": False,
               "stages": {"market_acquisition": "NOT_EXECUTED_FROZEN_OFFICIAL_OHLC",
                          "prediction_generation": "NOT_EXECUTED_FROZEN_PUBLIC_FORECAST",
                          "canonical_evaluation": "EXECUTED", "quality_gate": "EXECUTED",
                          "dashboard_renderer": "EXECUTED", "line_renderer": "EXECUTED", "email_renderer": "EXECUTED",
                          "publication": "NOT_EXECUTED", "transport": "NOT_EXECUTED"}}
    # Terminal receipt is written last; incomplete rendering/output cannot
    # leave a success receipt behind.
    return {"correction.json": corrected, "index.html": html,
            "line.txt": line, "email.txt": email, "receipt.json": receipt}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-open-input", type=Path, required=True)
    parser.add_argument("--post-close-input", type=Path, required=True)
    parser.add_argument("--expected-pre-id", required=True)
    parser.add_argument("--expected-post-id", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--correction-revision", type=int, required=True)
    parser.add_argument("--dashboard-url", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    # Existing roots, repository/runtime/archive/dashboard and input ancestors
    # are forbidden. Each invocation owns a fresh isolated directory.
    forbidden = {"artifacts", "archive", "latest", "dashboard", "templates", "public", "data"}
    if output.exists() or ROOT == output or ROOT in output.parents or forbidden.intersection(output.parts):
        raise ValueError("CORRECTION_OUTPUT_NOT_ISOLATED")
    inputs = [args.pre_open_input.resolve(), args.post_close_input.resolve()]
    if any(output == p or output in p.parents for p in inputs):
        raise ValueError("CORRECTION_INPUT_WRITEBACK_FORBIDDEN")
    values = [json.loads(p.read_text(encoding="utf-8")) for p in inputs]
    result = prepare(*values, session=args.session, revision=args.correction_revision,
                     expected_pre_id=args.expected_pre_id, expected_post_id=args.expected_post_id,
                     dashboard_url=args.dashboard_url)
    output.mkdir(parents=True, exist_ok=False)
    for name, content in result.items():
        with (output / name).open("x", encoding="utf-8") as stream:
            stream.write(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, sort_keys=True, indent=2))
    print(json.dumps({"status": "ISOLATED_CORRECTION_VALIDATED", "correction_id": result["receipt.json"]["correction_id"],
                      "output_dir": str(output), "notification_sent": False}))


if __name__ == "__main__":
    main()
