from datetime import datetime, timedelta

import pandas as pd

from app.loaders.google_sheet_loader import load_stock_ids_with_provenance
from app.market.shioaji_client import classify_shioaji_error, get_api
from app.market.historical_price_loader import get_historical_prices
from app.market.historical_normalizer import minute_to_daily
from app.market.historical_storage import inspect_historical_csv, save_historical_to_csv
from app.market.tw_history_admission import public_admission, validate_history_candidate


MIN_TECHNICAL_BARS = 20


def fetch_yfinance_daily(stock_id, start_date, end_date, downloader=None):
    """Fetch a credential-free TW fallback, trying listed then OTC suffix.

    ``downloader`` is injectable so deterministic validators never use the
    network.  Directional/research interpretation remains downstream.
    """
    if downloader is None:
        import yfinance as yf
        downloader = yf.download
    failures = []
    for suffix in (".TW", ".TWO"):
        ticker = f"{str(stock_id).zfill(4)}{suffix}"
        try:
            frame = downloader(ticker, start=start_date, end=end_date, progress=False, auto_adjust=False, timeout=20)
            if frame is None or frame.empty:
                failures.append(f"{ticker}:empty")
                continue
            frame = frame.reset_index()
            if isinstance(frame.columns, pd.MultiIndex):
                frame.columns = [str(item[0]) for item in frame.columns]
            columns = {str(name).lower().replace(" ", "_"): name for name in frame.columns}
            required = {"date", "open", "high", "low", "close", "volume"}
            if not required.issubset(columns):
                failures.append(f"{ticker}:columns")
                continue
            normalized = pd.DataFrame({
                "date": pd.to_datetime(frame[columns["date"]], errors="coerce").dt.date,
                "open": pd.to_numeric(frame[columns["open"]], errors="coerce"),
                "high": pd.to_numeric(frame[columns["high"]], errors="coerce"),
                "low": pd.to_numeric(frame[columns["low"]], errors="coerce"),
                "close": pd.to_numeric(frame[columns["close"]], errors="coerce"),
                "volume": pd.to_numeric(frame[columns["volume"]], errors="coerce"),
            }).dropna(subset=["date", "open", "high", "low", "close"])
            admission = validate_history_candidate(normalized, source=f"yfinance:{ticker}", target_date=end_date, minimum_bars=MIN_TECHNICAL_BARS)
            if admission["admission_success"]:
                return admission["normalized"], ticker, failures
            failures.append(f"{ticker}:{admission['status']}:{admission['row_count']}")
        except Exception as exc:
            failures.append(f"{ticker}:{exc.__class__.__name__}")
    return pd.DataFrame(), None, failures


def _fallback_history(stock_id, start_date, end_date, *, downloader=None):
    existing = inspect_historical_csv(stock_id, target_date=end_date, minimum_bars=MIN_TECHNICAL_BARS)
    bars_before = int(existing.get("row_count") or 0)
    frame, ticker, failures = fetch_yfinance_daily(stock_id, start_date, end_date, downloader=downloader)
    if not frame.empty:
        admission = validate_history_candidate(frame, source=f"yfinance:{ticker}", target_date=end_date, minimum_bars=MIN_TECHNICAL_BARS)
        path = save_historical_to_csv(frame, stock_id)
        return {
            "usable": True, "source": "yfinance_tw_reference", "ticker": ticker,
            "csv_path": path, "latest_date": str(frame["date"].max()),
            "bars_before": bars_before, "bars_after": len(frame), "failures": failures,
            "admission": public_admission(admission),
        }
    return {
        "usable": bool(existing.get("usable")), "source": "existing_historical_csv",
        "ticker": None, "csv_path": existing.get("csv_path"), "latest_date": existing.get("latest_date"),
        "bars_before": bars_before, "bars_after": bars_before, "failures": failures,
        "warning": existing.get("warning"),
        "admission": existing.get("admission"),
    }


def _warning(code, message, stock_id=None, severity="warning", source="historical_csv_update"):
    payload = {
        "code": code,
        "severity": severity,
        "source": source,
        "message": message,
    }
    if stock_id is not None:
        payload["stock_id"] = str(stock_id).zfill(4)
    return payload


def _empty_status(start_date, end_date):
    return {
        "schema_version": "pipeline_pre_delivery_status_v1",
        "stage": "historical_csv_update",
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "completed_at": None,
        "requested_start_date": start_date,
        "requested_end_date": end_date,
        "shioaji_available": False,
        "shioaji_error_classification": None,
        "historical_update_attempted": False,
        "historical_update_completed": False,
        "updated_count": 0,
        "fallback_count": 0,
        "missing_count": 0,
        "failed_count": 0,
        "report_ready_available": False,
        "fallback_policy": {
            "enabled": True,
            "fallback_order": ["yfinance_tw_reference", "existing_historical_csv"],
            "bounded_kbars_window_days": 180,
            "minimum_technical_bars": MIN_TECHNICAL_BARS,
            "crash_pipeline_on_shioaji_failure": False,
        },
        "warnings": [],
        "stocks": [],
    }


def bootstrap_symbol_history(stock_id, *, target_date=None, yfinance_downloader=None):
    """Idempotently bootstrap one missing TW historical CSV.

    Existing files are never overwritten by this onboarding helper.  Provider
    ownership remains the existing Shioaji -> yfinance fallback contract.
    """

    stock_id = str(stock_id).strip().zfill(4)
    target_date = str(target_date or datetime.today().strftime("%Y-%m-%d"))
    existing = inspect_historical_csv(
        stock_id, target_date=target_date, minimum_bars=MIN_TECHNICAL_BARS,
    )
    if existing.get("exists"):
        return {
            "schema_version": "tw_historical_bootstrap_result_v1",
            "stock_id": stock_id,
            "success": bool(existing.get("usable")),
            "attempted": False,
            "result": "noop_existing_usable" if existing.get("usable") else "existing_historical_insufficient",
            "csv_path": existing.get("csv_path"),
        }

    status = main(
        raise_on_failure=False,
        stock_ids=[stock_id],
        universe_evidence={
            "source": "new_symbol_historical_bootstrap",
            "fallback_used": False,
            "stock_count": 1,
            "market": "TW",
        },
        yfinance_downloader=yfinance_downloader,
    )
    final = inspect_historical_csv(
        stock_id, target_date=target_date, minimum_bars=MIN_TECHNICAL_BARS,
    )
    return {
        "schema_version": "tw_historical_bootstrap_result_v1",
        "stock_id": stock_id,
        "success": bool(final.get("usable")),
        "attempted": True,
        "result": "bootstrap_success" if final.get("usable") else "bootstrap_failed",
        "csv_path": final.get("csv_path"),
        "reason": final.get("warning"),
        "provider_status": status.get("stocks", [{}])[0].get("update_status") if status.get("stocks") else None,
    }


def main(raise_on_failure=False, stock_ids=None, universe_evidence=None, yfinance_downloader=None):
    if stock_ids is None:
        stock_ids, universe_evidence = load_stock_ids_with_provenance()

    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=180)).strftime("%Y-%m-%d")
    status = _empty_status(start_date, end_date)
    status["stock_universe"] = universe_evidence or {
        "source": "caller_supplied", "fallback_used": False,
        "stock_count": len(stock_ids), "market": "TW", "window": "pre_open_0700",
    }

    try:
        api = get_api()
        status["shioaji_available"] = True
        status["historical_update_attempted"] = True
    except Exception as exc:
        classification = getattr(exc, "classification", classify_shioaji_error(exc))
        status["shioaji_error_classification"] = classification
        status["warnings"].append(
            _warning(
                classification,
                "Shioaji login/runtime unavailable; using existing historical CSV fallback where present.",
                severity="error",
                source="shioaji_login",
            )
        )
        api = None

    for stock_id in stock_ids:
        stock_id = str(stock_id).zfill(4)
        stock_status = {
            "stock_id": stock_id,
            "update_status": "not_attempted",
            "fallback_used": False,
            "fallback_usable": False,
            "csv_path": None,
            "latest_date": None,
            "warning": None,
        }

        print(f"開始更新歷史資料：{stock_id}")

        if api is None:
            csv_status = _fallback_history(stock_id, start_date, end_date, downloader=yfinance_downloader)
            stock_status.update(
                {
                    "update_status": f"fallback_{csv_status['source']}",
                    "fallback_used": True,
                    "fallback_usable": csv_status["usable"],
                    "csv_path": csv_status["csv_path"],
                    "latest_date": csv_status["latest_date"],
                    "warning": csv_status.get("warning"),
                    "fallback_source": csv_status["source"],
                    "bars_before": csv_status["bars_before"], "bars_after": csv_status["bars_after"],
                    "fallback_failures": csv_status.get("failures", []),
                    "history_admission": csv_status.get("admission"),
                }
            )
            if csv_status["usable"]:
                status["fallback_count"] += 1
                print(f"Shioaji 不可用，使用 {csv_status['source']}：{csv_status['csv_path']}")
            else:
                status["missing_count"] += 1
                status["warnings"].append(
                    _warning(
                        "historical_csv_fallback_unavailable",
                        "Shioaji unavailable and no usable historical CSV fallback exists.",
                        stock_id=stock_id,
                    )
                )
                print(f"Shioaji 不可用且無可用 historical CSV：{stock_id}")
            status["stocks"].append(stock_status)
            continue

        try:
            minute_df = get_historical_prices(
                api=api,
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date,
            )

            daily_df = minute_to_daily(minute_df)
            admission = validate_history_candidate(daily_df, source="shioaji_kbars", target_date=end_date, minimum_bars=MIN_TECHNICAL_BARS)
            stock_status["fetch_success"] = True
            stock_status["history_admission"] = public_admission(admission)
            if not admission["admission_success"]:
                raise ValueError(f"history_admission:{admission['status']}")
            csv_path = save_historical_to_csv(admission["normalized"], stock_id)
            status["updated_count"] += 1
            stock_status.update(
                {
                    "update_status": "updated_from_shioaji",
                    "csv_path": csv_path,
                    "latest_date": str(daily_df["date"].max()) if not daily_df.empty else None,
                    "admission_success": True,
                }
            )

            print(f"完成：{csv_path}")
        except Exception as exc:
            classification = classify_shioaji_error(exc)
            csv_status = _fallback_history(stock_id, start_date, end_date, downloader=yfinance_downloader)
            stock_status.update(
                {
                    "update_status": f"fallback_{csv_status['source']}_after_fetch_error",
                    "fallback_used": True,
                    "fallback_usable": csv_status["usable"],
                    "csv_path": csv_status["csv_path"],
                    "latest_date": csv_status["latest_date"],
                    "warning": classification, "fallback_source": csv_status["source"],
                    "bars_before": csv_status["bars_before"], "bars_after": csv_status["bars_after"],
                    "fallback_failures": csv_status.get("failures", []),
                    "history_admission": csv_status.get("admission"),
                }
            )
            status["failed_count"] += 1
            status["warnings"].append(
                _warning(
                    classification,
                    "Shioaji Kbars fetch failed; using existing historical CSV fallback where present.",
                    stock_id=stock_id,
                    source="shioaji_kbars",
                )
            )
            if csv_status["usable"]:
                status["fallback_count"] += 1
                print(f"Kbars 失敗，沿用既有 historical CSV：{csv_status['csv_path']}")
            else:
                status["missing_count"] += 1
                print(f"Kbars 失敗且無可用 historical CSV：{stock_id}")
                if raise_on_failure:
                    raise
        status["stocks"].append(stock_status)

    status["historical_update_completed"] = (
        status["historical_update_attempted"] and status["failed_count"] == 0
    )
    status["report_ready_available"] = status["updated_count"] + status["fallback_count"] > 0
    status["completed_at"] = datetime.now().isoformat(timespec="seconds")
    return status


if __name__ == "__main__":
    main()
