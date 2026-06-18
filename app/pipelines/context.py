from datetime import datetime


def create_pipeline_context(pipeline_type):
    now = datetime.now()
    run_date = now.strftime("%Y-%m-%d")
    run_time = now.strftime("%H:%M:%S")
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    return {
        "pipeline_type": pipeline_type,
        "pipeline_run_id": f"{timestamp}_{pipeline_type}",
        "run_date": run_date,
        "run_time": run_time,
        "created_at": now.isoformat(timespec="seconds"),
    }
