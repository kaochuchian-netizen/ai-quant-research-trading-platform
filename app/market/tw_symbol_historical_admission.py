"""Per-symbol historical readiness for TW batch admission.

This module owns no provider logic.  It coordinates the existing historical
bootstrap contract and emits deterministic, presentation-safe diagnostics.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from app.market.historical_storage import inspect_historical_csv


def normalize_tw_symbol(value: Any) -> str:
    return str(value or "").strip().zfill(4)


def admit_tw_symbols_with_history(
    symbols: Iterable[Any],
    *,
    target_date: str,
    inspector: Callable[..., dict[str, Any]] = inspect_historical_csv,
    bootstrapper: Callable[..., dict[str, Any]] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Return admitted symbols and bounded per-symbol historical diagnostics.

    A missing CSV gets one bootstrap attempt.  An existing but insufficient
    CSV is never overwritten by this onboarding path.  Failures are isolated
    to the affected symbol.
    """

    if bootstrapper is None:
        from scripts.update_historical_csv import bootstrap_symbol_history

        bootstrapper = bootstrap_symbol_history

    admitted: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    for raw_symbol in symbols:
        symbol = normalize_tw_symbol(raw_symbol)
        before = inspector(symbol, target_date=target_date)
        diagnostic = {
            "symbol": symbol,
            "status": None,
            "readiness_status": None,
            "exclusion_stage": None,
            "exclusion_reason": None,
            "historical_path": before.get("csv_path"),
            "bootstrap_attempted": False,
            "bootstrap_result": "not_required",
            "history_row_count": int(before.get("row_count") or 0),
            "history_latest_date": before.get("latest_date"),
        }
        if before.get("usable"):
            diagnostic.update(status="ADMITTED", readiness_status="LIVE_READY")
            admitted.append(symbol)
            diagnostics.append(diagnostic)
            continue

        if before.get("exists"):
            diagnostic.update(
                status="HISTORICAL_INSUFFICIENT",
                readiness_status="HISTORICAL_INSUFFICIENT",
                exclusion_stage="historical_data_admission",
                exclusion_reason=before.get("warning") or "historical_csv_insufficient",
            )
            diagnostics.append(diagnostic)
            continue

        diagnostic.update(
            readiness_status="HISTORICAL_BOOTSTRAP_REQUIRED",
            bootstrap_attempted=True,
        )
        try:
            bootstrap = bootstrapper(symbol, target_date=target_date)
        except Exception as exc:  # one symbol must not abort the universe
            bootstrap = {"success": False, "result": f"failed:{exc.__class__.__name__}"}
        after = inspector(symbol, target_date=target_date)
        diagnostic.update(
            historical_path=after.get("csv_path") or diagnostic["historical_path"],
            history_row_count=int(after.get("row_count") or 0),
            history_latest_date=after.get("latest_date"),
            bootstrap_result=str(bootstrap.get("result") or ("success" if bootstrap.get("success") else "failed")),
        )
        if bootstrap.get("success") and after.get("usable"):
            diagnostic.update(status="ADMITTED")
            admitted.append(symbol)
        else:
            diagnostic.update(
                status="HISTORICAL_BOOTSTRAP_FAILED",
                exclusion_stage="historical_data_admission",
                exclusion_reason=after.get("warning") or bootstrap.get("reason") or "historical_bootstrap_failed",
            )
        diagnostics.append(diagnostic)
    return admitted, diagnostics
