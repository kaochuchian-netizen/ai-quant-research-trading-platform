#!/usr/bin/env python3
"""Deterministic AI-DEV-228 historical onboarding and checkout closure gate."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.market.historical_storage import inspect_historical_csv
from app.market.tw_symbol_historical_admission import admit_tw_symbols_with_history
from scripts.orchestrator.validate_post_merge_status import summarize_post_merge_status


def history() -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-08-31", periods=30)
    return pd.DataFrame({
        "date": dates.date,
        "open": range(100, 130), "high": range(101, 131),
        "low": range(99, 129), "close": range(100, 130), "volume": [1000] * 30,
    })


def post_merge_fixture(*, branch="main", head="same", main="same", origin="same") -> dict:
    return {
        "ok": True, "warnings": [], "open_pr_count": 0,
        "git": {
            "current_branch": branch, "head_sha": head, "main_sha": main, "origin_main_sha": origin,
            "clean": True, "status_short": [],
            "main_origin_main_sync": {"status": "in_sync", "ahead": 0, "behind": 0},
            "local_branches": ["main"], "remote_branches": ["origin/main"],
        },
        "runtime": {"pending_queue": {"pending_count": 0}, "handoff_diagnostics": {"classification": "no_active_handoff"}},
    }


def main() -> int:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)

        def inspector(symbol, **kwargs):
            return inspect_historical_csv(symbol, folder=str(folder), **kwargs)

        attempts: list[str] = []

        def successful_bootstrap(symbol, **_):
            attempts.append(symbol)
            history().to_csv(folder / f"{symbol}_daily.csv", index=False)
            return {"success": True, "result": "bootstrap_success"}

        admitted, diagnostics = admit_tw_symbols_with_history(
            ["2330", "3293", "009816"], target_date="2026-09-01",
            inspector=inspector, bootstrapper=successful_bootstrap,
        )
        checks["new_symbol_bootstrap_reaches_downstream"] = admitted == ["2330", "3293", "009816"]
        checks["leading_zero_preserved"] = diagnostics[-1]["symbol"] == "009816"
        checks["explicit_success_diagnostics"] = all(
            item["status"] == "ADMITTED" and item["bootstrap_attempted"] for item in diagnostics
        )

        attempts.clear()
        admitted_again, replay = admit_tw_symbols_with_history(
            ["3293"], target_date="2026-09-01", inspector=inspector,
            bootstrapper=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not bootstrap")),
        )
        checks["idempotent_noop"] = admitted_again == ["3293"] and not replay[0]["bootstrap_attempted"]

        def failed_bootstrap(symbol, **_):
            if symbol == "4743":
                return {"success": False, "result": "provider_unavailable", "reason": "provider_unavailable"}
            history().to_csv(folder / f"{symbol}_daily.csv", index=False)
            return {"success": True, "result": "bootstrap_success"}

        admitted_isolated, failed = admit_tw_symbols_with_history(
            ["4743", "2305"], target_date="2026-09-01", inspector=inspector, bootstrapper=failed_bootstrap,
        )
        excluded = failed[0]
        checks["per_symbol_failure_isolated"] = admitted_isolated == ["2305"]
        checks["exclusion_diagnostics_complete"] = (
            excluded["status"] == "HISTORICAL_BOOTSTRAP_FAILED"
            and excluded["exclusion_stage"] == "historical_data_admission"
            and excluded["historical_path"].endswith("4743_daily.csv")
            and excluded["bootstrap_attempted"]
            and excluded["bootstrap_result"] == "provider_unavailable"
        )

    stale = summarize_post_merge_status(post_merge_fixture(branch="ai-dev/227-old", head="feature"))
    mismatch = summarize_post_merge_status(post_merge_fixture(head="old", main="new", origin="new"))
    healthy = summarize_post_merge_status(post_merge_fixture())
    checks["stale_feature_checkout_rejected"] = not stale["ok"]
    checks["main_origin_identity_mismatch_rejected"] = not mismatch["ok"]
    checks["closed_main_checkout_accepted"] = healthy["ok"]
    checks["no_symbol_hardcode_in_implementation"] = "3293" not in Path(
        "app/market/tw_symbol_historical_admission.py"
    ).read_text(encoding="utf-8")

    report = {
        "schema_version": "validate_ai_dev_228_tw_new_symbol_historical_bootstrap_v1",
        "checks": checks, "passed": sum(checks.values()), "total": len(checks), "ok": all(checks.values()),
        "production_mutation": False,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
