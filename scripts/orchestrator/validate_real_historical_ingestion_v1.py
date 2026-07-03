#!/usr/bin/env python3
"""Validate AI-DEV-129 real historical ingestion and rolling evaluation V1.

The validator is offline and read-only except for temporary files under /tmp used to
exercise malformed JSON scanning. It never runs production pipelines or delivery.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.history.artifact_normalizer import normalize_artifact
from app.history.artifact_scanner import missing_path_result, scan_artifacts
from app.history.completeness import build_completeness_summary
from app.history.historical_store import build_historical_store
from app.rolling.rolling_calibration import build_rolling_calibration_readiness
from app.rolling.rolling_dashboard_summary import build_dashboard_ready_summary
from app.rolling.rolling_evaluation import build_rolling_evaluation
from app.rolling.rolling_factor_effectiveness import build_rolling_factor_effectiveness_readiness
from app.rolling.rolling_windows import build_rolling_windows

REQUIRED_FILES = [
    'app/history/__init__.py',
    'app/history/schemas.py',
    'app/history/artifact_scanner.py',
    'app/history/artifact_classifier.py',
    'app/history/artifact_normalizer.py',
    'app/history/historical_store.py',
    'app/history/deduplication.py',
    'app/history/completeness.py',
    'app/rolling/__init__.py',
    'app/rolling/schemas.py',
    'app/rolling/rolling_windows.py',
    'app/rolling/rolling_evaluation.py',
    'app/rolling/rolling_calibration.py',
    'app/rolling/rolling_factor_effectiveness.py',
    'app/rolling/rolling_dashboard_summary.py',
    'scripts/orchestrator/ingest_real_historical_artifacts.py',
    'scripts/orchestrator/build_rolling_evaluation_artifact.py',
    'scripts/orchestrator/validate_real_historical_ingestion_v1.py',
    'templates/real_historical_artifact_input.example.json',
    'templates/historical_artifact_store.example.json',
    'templates/rolling_evaluation_artifact.example.json',
    'templates/rolling_dashboard_summary.example.json',
    'docs/ai_dev_129_real_historical_artifact_ingestion_rolling_evaluation_v1.md',
    'docs/runbooks/real_historical_artifact_ingestion_runbook.md',
]


def run_json(command: list[str]) -> tuple[int, dict[str, Any], str]:
    proc = subprocess.run(command, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    try:
        payload = json.loads(proc.stdout)
    except Exception as exc:
        payload = {'parse_error': str(exc), 'stdout': proc.stdout, 'stderr': proc.stderr}
    return proc.returncode, payload, proc.stderr


def expect(condition: bool, reasons: list[str], message: str) -> None:
    if not condition:
        reasons.append(message)


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate AI-DEV-129 real historical ingestion V1')
    parser.add_argument('--pretty', action='store_true')
    args = parser.parse_args()
    reasons: list[str] = []

    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    expect(not missing, reasons, f'missing required files: {missing}')

    for rel in [
        'templates/real_historical_artifact_input.example.json',
        'templates/historical_artifact_store.example.json',
        'templates/rolling_evaluation_artifact.example.json',
        'templates/rolling_dashboard_summary.example.json',
    ]:
        if (ROOT / rel).exists():
            try:
                json.loads((ROOT / rel).read_text(encoding='utf-8'))
            except Exception as exc:
                reasons.append(f'example JSON failed to load: {rel}: {exc}')

    missing_scan = missing_path_result('/tmp/ai-dev-129-path-does-not-exist')
    expect(missing_scan['found_count'] == 0 and missing_scan['warnings'], reasons, 'scanner must handle missing path')

    with TemporaryDirectory(prefix='ai-dev-129-') as temp_dir:
        malformed = Path(temp_dir) / 'malformed.json'
        malformed.write_text('{bad json', encoding='utf-8')
        unknown = Path(temp_dir) / 'unknown.json'
        unknown.write_text(json.dumps({'schema_version': 'unknown_v1', 'value': 1}), encoding='utf-8')
        scan = scan_artifacts([temp_dir], source_kind='offline_sample')
        expect(scan['malformed_count'] >= 1, reasons, 'scanner must classify malformed JSON')
        expect(scan['unsupported_count'] >= 1, reasons, 'scanner must classify unknown artifacts')

    approved = normalize_artifact({'schema_version':'approved_scheduler_delivery_v1','run_id':'approved-1','scheduler_window':'post_close_1500','pipeline_type':'post_close','generated_at':'2026-07-03T15:00:00+08:00'}, source_path='offline://approved', source_kind='offline_sample')
    prediction = normalize_artifact({'schema_version':'prediction_snapshot_v1','run_id':'pred-1','stock_id':'2330','prediction_target':'next_day_high_low'}, source_path='offline://prediction', source_kind='offline_sample')
    evaluation = normalize_artifact({'schema_version':'prediction_evaluation_v1','run_id':'eval-1','stock_id':'2330','direction_hit':True,'actual_return_1d':0.01}, source_path='offline://evaluation', source_kind='offline_sample')
    dashboard = normalize_artifact({'schema_version':'dashboard_intelligence_v1','run_id':'dash-1','production_publish_allowed':False}, source_path='offline://dashboard', source_kind='offline_sample')
    incident = normalize_artifact('incident diagnostic text pre_open_0700_hung', source_path='offline://incident', source_kind='offline_sample')
    expect(approved.artifact_type == 'approved_delivery', reasons, 'normalizer handles approved delivery artifact')
    expect(prediction.artifact_type == 'prediction_snapshot', reasons, 'normalizer handles prediction snapshot artifact')
    expect(evaluation.artifact_type == 'evaluation', reasons, 'normalizer handles evaluation artifact')
    expect(dashboard.artifact_type == 'dashboard_intelligence', reasons, 'normalizer handles dashboard intelligence artifact')
    expect(incident.artifact_type == 'incident_diagnostic', reasons, 'normalizer handles incident diagnostic text')

    records = [approved.to_dict(), prediction.to_dict(), evaluation.to_dict(), dashboard.to_dict(), incident.to_dict(), approved.to_dict()]
    store = build_historical_store(records).to_dict()
    expect(store['deduplication_summary']['duplicate_count'] >= 1, reasons, 'deduplication must be idempotent')

    completeness = build_completeness_summary(records)
    expect('pre_open_0700' in completeness['by_scheduler_window'], reasons, 'completeness must include scheduler windows')
    expect(completeness['by_artifact_type'].get('found', {}).get('prediction_snapshot', 0) >= 1, reasons, 'completeness must count artifact types')

    ingest_rc, ingest_json, ingest_err = run_json([sys.executable, 'scripts/orchestrator/ingest_real_historical_artifacts.py'])
    expect(ingest_rc == 0 and ingest_json.get('schema_version') == 'historical_artifact_store_v1', reasons, f'ingestion script must print valid JSON: {ingest_err}')
    expect(ingest_json.get('sample_mode') is True, reasons, 'offline ingestion must mark sample_mode=true')
    expect(ingest_json.get('deduplication_summary', {}).get('duplicate_count', 0) >= 1, reasons, 'offline sample must include duplicate summary')
    status_counts = ingest_json.get('index', {}).get('by_status', {})
    expect(status_counts.get('pending', 0) >= 1, reasons, 'completeness must identify pending records')
    expect(status_counts.get('insufficient_data', 0) >= 1, reasons, 'completeness must identify insufficient records')

    build_rc, artifact, build_err = run_json([sys.executable, 'scripts/orchestrator/build_rolling_evaluation_artifact.py'])
    expect(build_rc == 0 and artifact.get('schema_version') == 'rolling_evaluation_artifact_v1', reasons, f'rolling artifact builder must print valid JSON: {build_err}')
    windows = artifact.get('rolling_windows', [])
    window_ids = {w.get('window_id') for w in windows if isinstance(w, dict)}
    for key in ['last_7_records','last_20_records','last_60_records','all_available']:
        expect(key in window_ids, reasons, f'rolling window missing: {key}')
    expect(artifact.get('input_summary', {}).get('sample_mode') is True, reasons, 'rolling artifact must mark sample_mode=true for offline sample')
    expect(artifact.get('rolling_evaluation', {}).get('status') in {'partial','insufficient','not_available'}, reasons, 'insufficient sample must not be overclaimed as ready')
    expect(artifact.get('rolling_calibration_readiness', {}).get('calibration_status') in {'demo_only','insufficient_sample','not_available'}, reasons, 'calibration readiness must not claim over/under confidence without enough real data')
    expect(artifact.get('rolling_factor_effectiveness_readiness', {}).get('production_mutation_allowed') is False, reasons, 'factor readiness must not allow production mutation')
    expect(artifact.get('dashboard_ready_summary', {}).get('production_publish_allowed') is False, reasons, 'dashboard summary must not allow production publish')
    expect(artifact.get('dashboard_ready_summary', {}).get('advisory_only') is True, reasons, 'dashboard summary must be advisory only')

    direct_windows = build_rolling_windows(store['records'])
    direct_eval = build_rolling_evaluation(store['records'], sample_mode=True)
    direct_calibration = build_rolling_calibration_readiness(store['records'], sample_mode=True)
    direct_factor = build_rolling_factor_effectiveness_readiness(store['records'], sample_mode=True)
    direct_dashboard = build_dashboard_ready_summary(store, direct_windows, direct_eval, direct_calibration, direct_factor, sample_mode=True)
    expect(direct_factor['production_mutation_allowed'] is False, reasons, 'direct factor readiness must forbid production mutation')
    expect(direct_dashboard['production_publish_allowed'] is False, reasons, 'direct dashboard summary must forbid production publishing')

    safety = artifact.get('safety_summary', {})
    forbidden_flags = [
        'broker_login','simulation_order','production_order','line_sent','email_sent','dashboard_published',
        'production_db_write','secrets_read','production_pipeline_run','trading_execution','backtesting_runtime_execution'
    ]
    for key in forbidden_flags:
        expect(safety.get(key) is False, reasons, f'safety flag must be false: {key}')
    expect(safety.get('production_publish_allowed') is False, reasons, 'production_publish_allowed must be false')
    expect(safety.get('production_mutation_allowed') is False, reasons, 'production_mutation_allowed must be false')

    result = {
        'ok': not reasons,
        'passed': not reasons,
        'reasons': reasons,
        'checks': {
            'required_files': len(REQUIRED_FILES) - len(missing),
            'ingested_records': len(ingest_json.get('records', [])) if isinstance(ingest_json, dict) else 0,
            'rolling_windows': sorted(window_ids) if 'window_ids' in locals() else [],
            'sample_mode': artifact.get('input_summary', {}).get('sample_mode') if isinstance(artifact, dict) else None,
            'dashboard_publish_allowed': artifact.get('dashboard_ready_summary', {}).get('production_publish_allowed') if isinstance(artifact, dict) else None,
        },
        'side_effects': {
            'production_pipeline_run': False,
            'line_sent': False,
            'email_sent': False,
            'dashboard_published': False,
            'secrets_read': False,
            'trading_execution_run': False,
            'production_db_write': False,
            'backtesting_runtime_execution': False,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write('\n')
    return 0 if not reasons else 2

if __name__ == '__main__':
    raise SystemExit(main())
