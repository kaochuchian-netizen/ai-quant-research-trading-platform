#!/usr/bin/env python3
"""Repo-local AI-DEV-160 delivery timeout/late suppression simulations."""
from __future__ import annotations
import argparse, json, sys
from datetime import timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.orchestrator import approved_pre_open_delivery as delivery

def simulate() -> dict:
    base = delivery.scheduled_datetime_taipei('intraday_1305', delivery.now_taipei())
    timeout = delivery.timeout_delivery_artifact('intraday_1305', delivery.window_timeout_seconds('intraday_1305'), base.isoformat())
    within = delivery.delivery_lateness('intraday_1305', base + timedelta(minutes=8))
    late = delivery.delivery_lateness('intraday_1305', base + timedelta(minutes=35))
    late_artifact = delivery.late_delivery_artifact('intraday_1305', late, (base + timedelta(minutes=35)).isoformat())
    failed = {'window': 'intraday_1305', 'status': 'pipeline_failed_delivery_skipped', 'pipeline_completed': False, 'delivery_attempted': False, 'line_attempted': False, 'email_attempted': False, 'dashboard_publish_attempted': False, 'reason': 'child_pipeline_failed'}
    return {'schema_version': 'intraday_delivery_timeout_guard_simulation_v1', 'task_id': 'AI-DEV-160', 'scenarios': {'child_pipeline_timeout': timeout, 'pipeline_completed_within_grace_period': {'late_delivery_suppressed': within['late'], **within}, 'pipeline_completed_after_grace_period': late_artifact, 'pipeline_failed': failed}, 'safety': {'line_sent': False, 'email_sent': False, 'production_pipeline_run': False, 'db_write': False, 'scheduler_modified': False, 'dashboard_published': False}, 'ok': True}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pretty', action='store_true')
    args = parser.parse_args()
    print(json.dumps(simulate(), ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
