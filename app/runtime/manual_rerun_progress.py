"""Task-scoped progress events for governed manual reruns."""
from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo


PROGRESS_LOG_ENV = "STOCK_AI_MANUAL_RERUN_PROGRESS_LOG"
CANONICAL_STAGES = (
    "runtime_started",
    "market_data",
    "news_acquisition",
    "research_rre",
    "prediction_projection",
    "artifact_generation",
    "admission",
    "archive_publish",
    "chromium_visual",
    "notification",
    "completed",
)


def report_manual_rerun_stage(stage: str, status: str = "started", **metadata: object) -> bool:
    if stage not in CANONICAL_STAGES:
        raise ValueError(f"unsupported manual rerun stage: {stage}")
    path = os.environ.get(PROGRESS_LOG_ENV)
    if not path:
        return False
    payload = {
        "schema_version": "manual_rerun_progress_event_v1",
        "stage": stage,
        "status": status,
        "at": datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat(),
        "metadata": {
            key: value for key, value in metadata.items()
            if key not in {"secret", "token", "pin", "password"}
        },
    }
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, encoded)
    finally:
        os.close(descriptor)
    return True
