#!/usr/bin/env python3
"""Validate AI-DEV-160 delivery timeout and dashboard cleanup contract."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.dashboard.four_window_route_integration import build_artifact, build_input, render_route_html
from scripts.orchestrator.simulate_intraday_delivery_timeout_guard_v1 import simulate
REQUIRED_FILES = ['scripts/orchestrator/approved_pre_open_delivery.py', 'app/dashboard/four_window_route_integration.py', 'scripts/orchestrator/simulate_intraday_delivery_timeout_guard_v1.py', 'scripts/orchestrator/validate_intraday_delivery_timeout_dashboard_cleanup_v1.py', 'docs/intraday_delivery_timeout_dashboard_cleanup_v1.md', 'docs/runbooks/intraday_delivery_timeout_dashboard_cleanup_runbook.md']
REQUIRED_MARKERS = ['13:05 盤中追蹤', '13:35 收盤快照', '今日資料尚未完成', '預測方法說明', '風險提醒', '重大新聞資料待接', '偏多', '不明朗', '中高', '樣本數：9', 'blocked_insufficient_sample', '單日檢討', '7 天滾動檢討']
FORBIDDEN_MAIN = ['source_evidence', 'read_mode', 'source_type', 'local_analysis_context', 'path', 'pipeline_type', 'pipeline_run_id', 'stock universe count', 'advisory_only', 'Artifact inventory', 'latest_ohlcv_date', 'missing_fields', 'deterministic_baseline_v1: 20D median range', 'production rating/action/confidence/weight']

def run_script(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return proc.returncode, proc.stdout

def render_html() -> str:
    artifact = build_artifact(build_input(), ROOT)
    return render_route_html(artifact, '')

def validate_delivery(reasons: list[str]) -> None:
    src = (ROOT / 'scripts/orchestrator/approved_pre_open_delivery.py').read_text(encoding='utf-8')
    for marker in ['WINDOW_TIMEOUT_SECONDS', 'intraday_1305": 10 * 60', 'WINDOW_GRACE_PERIOD_SECONDS', 'timeout_delivery_artifact', 'late_delivery_artifact', 'write_progress_artifact', 'delivery_lateness', 'late_delivery_suppressed']:
        if marker not in src:
            reasons.append(f'missing delivery marker: {marker}')
    sim = simulate(); timeout = sim['scenarios']['child_pipeline_timeout']; late = sim['scenarios']['pipeline_completed_after_grace_period']; within = sim['scenarios']['pipeline_completed_within_grace_period']; failed = sim['scenarios']['pipeline_failed']
    if timeout.get('line_attempted') is not False or timeout.get('email_attempted') is not False or timeout.get('dashboard_publish_attempted') is not False:
        reasons.append('timeout artifact must mark LINE/Email/Dashboard attempted false')
    if timeout.get('pipeline_completed') is not False or timeout.get('reason') != 'child_pipeline_timeout':
        reasons.append('timeout simulation schema invalid')
    if within.get('late_delivery_suppressed') is not False:
        reasons.append('within-grace simulation should not suppress')
    if late.get('late_delivery_suppressed') is not True or late.get('line_attempted') is not False or late.get('email_attempted') is not False:
        reasons.append('late suppression simulation invalid')
    if failed.get('line_attempted') is not False or failed.get('email_attempted') is not False:
        reasons.append('failed simulation must not send')
    if any(sim['safety'].values()):
        reasons.append('simulation safety flags must all be false')

def validate_dashboard(reasons: list[str]) -> None:
    html = render_html(); main = html.split('<details>', 1)[0]
    for marker in REQUIRED_MARKERS:
        if marker not in main:
            reasons.append(f'missing dashboard marker: {marker}')
    for token in FORBIDDEN_MAIN:
        if token in main:
            reasons.append(f'forbidden main UI token present: {token}')
    if main.count('deterministic baseline V1') < 1:
        reasons.append('deterministic baseline method marker missing')
    if main.count('風險提醒') != 1:
        reasons.append('common risk reminder must appear once')
    if '評等/動作：資料待接 / 資料待接' in main or '分數：資料待接' in main:
        reasons.append('tracking cards still spam pending rating/action/score')
    for raw in ['bullish', 'uncertain', 'medium_high', 'insufficient_data']:
        if raw in main:
            reasons.append(f'raw status leaked to main UI: {raw}')
    if '今日預測區間' not in main or '隔日預測區間' not in main:
        reasons.append('stock forecast card missing interval fields')

def validate_regression_commands(reasons: list[str]) -> list[dict[str, object]]:
    commands = [['scripts/orchestrator/validate_line_runtime_activation_guard_v1.py', '--pretty'], ['scripts/orchestrator/validate_line_and_dashboard_card_content_cleanup_v1.py', '--pretty'], ['scripts/orchestrator/validate_review_card_pm_readable_rendering_v1.py', '--pretty'], ['scripts/orchestrator/validate_formal_forecast_snapshot_accumulation_v1.py', '--pretty'], ['scripts/orchestrator/validate_forecast_calibration_proposal_v1.py', '--pretty'], ['scripts/orchestrator/validate_formal_forecast_backtest_report_v1.py', '--pretty'], ['scripts/orchestrator/validate_formal_forecast_value_engine_v1.py', '--pretty'], ['scripts/orchestrator/validate_formal_prediction_runtime_artifact_v1.py', '--pretty'], ['scripts/orchestrator/validate_formal_prediction_review_runtime_artifact_v1.py', '--pretty'], ['scripts/orchestrator/validate_dashboard_decision_state_semantics_v1.py', '--pretty'], ['scripts/orchestrator/validate_four_window_dashboard_runtime_data_binding_v1.py', '--pretty'], ['scripts/orchestrator/validate_multi_window_report_content_v1.py', '--pretty']]
    results = []
    for cmd in commands:
        code, _out = run_script(cmd); results.append({'command': ' '.join(cmd), 'returncode': code})
        if code != 0: reasons.append(f'regression validator failed: {cmd[0]}')
    return results

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--pretty', action='store_true'); parser.add_argument('--skip-regression-suite', action='store_true'); args = parser.parse_args(); reasons: list[str] = []
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists(): reasons.append(f'required file missing: {rel}')
    validate_delivery(reasons); validate_dashboard(reasons); regression = [] if args.skip_regression_suite else validate_regression_commands(reasons)
    output = {'ok': True, 'passed': not reasons, 'task_id': 'AI-DEV-160', 'regression_results': regression, 'reasons': reasons, 'side_effects': {'line_sent': False, 'email_sent': False, 'production_pipeline_run': False, 'python3_main_py': False, 'db_write': False, 'scheduler_modified': False, 'trading_or_order': False, 'secrets_read': False}}
    print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)); return 0 if output['passed'] else 2
if __name__ == '__main__':
    raise SystemExit(main())
