#!/usr/bin/env python3
"""Run a Codex-owned, isolated TW post-close replay from immutable input.

This is deliberately separate from the Portal manual-rerun bridge.  It never
fetches market data, rewrites a 07:00 prediction, updates ``latest`` or
overwrites an archive.  It reruns the canonical post-close quality projection,
Dashboard renderer and both channel renderers against one frozen input.

Default mode writes only to an explicitly supplied isolated output directory
and never sends.  Transport requires both ``--send`` and
``--confirmed-production-delivery``; channel receipts remain content-addressed
and fail closed through the existing delivery contract.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.market_dashboard_alias import snapshot_parity_contract
from app.reports.channel_delivery_receipt import delivery_identity
from app.reports.mobile_decision_presentation import (
    post_close_canonical_cards,
    post_close_canonical_lines,
    render_line,
    render_post_close_email,
    render_report,
)
from app.reports.post_close_quality_gate import batch_gate, evaluate_card
from scripts.orchestrator.approved_pre_open_delivery import (
    DEFAULT_MAIL_ENV_FILE,
    TW_POSTCLOSE_CHANNEL_RECEIPTS,
    send_concise_line,
    send_delivery_email,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trading-date", required=True)
    parser.add_argument("--window", choices=("post_close_1500",), required=True)
    parser.add_argument("--frozen-input", required=True)
    parser.add_argument("--output-dir", required=True, help="isolated, non-production replay output")
    parser.add_argument("--dashboard-url", required=True)
    parser.add_argument("--receipt-root", default=str(TW_POSTCLOSE_CHANNEL_RECEIPTS))
    parser.add_argument("--mail-env-file", default=str(DEFAULT_MAIL_ENV_FILE))
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--confirmed-production-delivery", action="store_true")
    return parser.parse_args()


def load_frozen_input(path: Path, *, trading_date: str, window: str) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    parity = snapshot_parity_contract(value)
    payload = value.get("payload") if isinstance(value.get("payload"), dict) else {}
    if not parity or value.get("effective_trading_date") != trading_date:
        raise ValueError("CODEX_REPLAY_FROZEN_IDENTITY_MISMATCH")
    if payload.get("market") not in {None, "TW"} or payload.get("window") not in {None, window}:
        raise ValueError("CODEX_REPLAY_WINDOW_MISMATCH")
    cards = post_close_canonical_cards(payload, "TW", window, require_frozen_universe=True)
    if not cards:
        raise ValueError("CODEX_REPLAY_EMPTY_FROZEN_UNIVERSE")
    return value


def prepare(snapshot: dict, *, trading_date: str, window: str, dashboard_url: str) -> dict:
    payload = snapshot["payload"]
    cards = post_close_canonical_cards(payload, "TW", window, require_frozen_universe=True)
    quality = batch_gate(cards, market="TW", window=window)
    if not quality["line_send_allowed"]:
        raise ValueError("CODEX_REPLAY_QUALITY_GATE_BLOCKED")
    line = render_line(payload, "TW", window, dashboard_url, require_frozen_universe=True)
    email = render_post_close_email(payload, "TW", window, dashboard_url)
    html = render_report(payload, "TW", window, "")
    parity = snapshot_parity_contract(snapshot)
    identity_base = {"snapshot_id": parity["snapshot_id"], "revision": parity["revision"], "payload_hash": parity["payload_hash"]}
    return {
        "schema_version": "codex_frozen_post_close_replay_v1",
        "mode": "FROZEN_INPUT_REPLAY",
        "trading_date": trading_date,
        "window": window,
        "snapshot": identity_base,
        "expected_symbols": [str(card.get("symbol") or card.get("stock_id")) for card in cards],
        "market_data": {"status": "FROZEN_OFFICIAL_OUTCOME_INPUT", "card_count": len(cards)},
        "analysis_prediction": {"status": "FROZEN_0700_IDENTITY_BOUND", "card_count": len(cards)},
        "evaluation": quality,
        "canonical_rows": post_close_canonical_lines(payload, "TW", window),
        "line": line,
        "email": email,
        "dashboard_html": html,
        "receipt_preview": {
            "line": delivery_identity(snapshot=snapshot, channel="line", market="TW", window=window, content=line),
            "email": delivery_identity(snapshot=snapshot, channel="email", market="TW", window=window, content=email),
        },
        "notification_attempted": False,
        "dashboard_latest_modified": False,
        "archive_modified": False,
    }


def write_isolated(result: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dashboard.html").write_text(result["dashboard_html"], encoding="utf-8")
    public = dict(result)
    public.pop("dashboard_html", None)
    (output_dir / "replay_result.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    if args.send and not args.confirmed_production_delivery:
        raise SystemExit("--confirmed-production-delivery is required with --send")
    snapshot = load_frozen_input(Path(args.frozen_input), trading_date=args.trading_date, window=args.window)
    result = prepare(snapshot, trading_date=args.trading_date, window=args.window, dashboard_url=args.dashboard_url)
    write_isolated(result, Path(args.output_dir))
    if args.send:
        result["email_delivery"] = send_delivery_email(
            Path(args.mail_env_file), args.window, "codex-frozen-replay", args.trading_date + "T15:00:00+08:00",
            "completed", args.dashboard_url, "", snapshot, Path(args.receipt_root), rendered_body=result["email"],
        )
        result["line_delivery"] = send_concise_line(
            args.window, args.trading_date + "T15:00:00+08:00", "completed", args.dashboard_url, "", snapshot,
            Path(args.receipt_root), rendered_message=result["line"],
        )
        result["notification_attempted"] = True
    print(json.dumps({key: value for key, value in result.items() if key != "dashboard_html"}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
