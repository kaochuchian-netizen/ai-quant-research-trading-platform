from datetime import datetime, timedelta

from app.loaders.google_sheet_loader import load_stock_ids
from app.market.shioaji_client import classify_shioaji_error, get_api
from app.market.historical_price_loader import get_historical_prices
from app.market.historical_normalizer import minute_to_daily
from app.market.historical_storage import inspect_historical_csv, save_historical_to_csv


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
            "fallback_source": "existing_historical_csv",
            "bounded_kbars_window_days": 30,
            "crash_pipeline_on_shioaji_failure": False,
        },
        "warnings": [],
        "stocks": [],
    }


def main(raise_on_failure=False):
    stock_ids = load_stock_ids()

    end_date = datetime.today().strftime("%Y-%m-%d")
    start_date = (datetime.today() - timedelta(days=180)).strftime("%Y-%m-%d")
    status = _empty_status(start_date, end_date)

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
            csv_status = inspect_historical_csv(stock_id)
            stock_status.update(
                {
                    "update_status": "fallback_existing_csv",
                    "fallback_used": True,
                    "fallback_usable": csv_status["usable"],
                    "csv_path": csv_status["csv_path"],
                    "latest_date": csv_status["latest_date"],
                    "warning": csv_status["warning"],
                }
            )
            if csv_status["usable"]:
                status["fallback_count"] += 1
                print(f"Shioaji 不可用，沿用既有 historical CSV：{csv_status['csv_path']}")
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
            csv_path = save_historical_to_csv(daily_df, stock_id)
            status["updated_count"] += 1
            stock_status.update(
                {
                    "update_status": "updated_from_shioaji",
                    "csv_path": csv_path,
                    "latest_date": str(daily_df["date"].max()) if not daily_df.empty else None,
                }
            )

            print(f"完成：{csv_path}")
        except Exception as exc:
            classification = classify_shioaji_error(exc)
            csv_status = inspect_historical_csv(stock_id)
            stock_status.update(
                {
                    "update_status": "fallback_existing_csv_after_fetch_error",
                    "fallback_used": True,
                    "fallback_usable": csv_status["usable"],
                    "csv_path": csv_status["csv_path"],
                    "latest_date": csv_status["latest_date"],
                    "warning": classification,
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
