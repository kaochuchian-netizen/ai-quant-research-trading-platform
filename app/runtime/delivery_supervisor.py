"""Whole-delivery deadline, run-scoped results and durable stage facts.

No analysis, publishing or transport is initiated by importing this module.
"""
from __future__ import annotations
import json
import hashlib
import os
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any
from app.runtime.manual_rerun_process_supervisor import run_process_group
from app.runtime.manual_rerun_progress import report_manual_rerun_stage

RUN_ENV = 'STOCK_AI_DELIVERY_RUN_ID'
FACT_ENV = 'STOCK_AI_DELIVERY_FACTS'

def run_identity(prefix: str) -> str:
    return os.environ.get(RUN_ENV) or f'{prefix}-{uuid.uuid4().hex}'

def checkpoint(stage: str, **facts: Any) -> None:
    report_manual_rerun_stage(stage)
    location = os.environ.get(FACT_ENV)
    if not location:
        return
    path = Path(location)
    retained = json.loads(path.read_text()) if path.exists() else {}
    retained.update(facts)
    retained.update(run_id=os.environ[RUN_ENV], stage=stage)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(retained, sort_keys=True))
    temporary.replace(path)

def supervise(command: list[str], *, cwd: Path, market: str, window: str,
              timeout_seconds: float, evidence_root: Path) -> dict[str, Any]:
    run_id = f'{market.lower()}-{window}-{uuid.uuid4().hex}'
    evidence_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix=run_id+'-', dir=evidence_root))
    result_path = directory / 'result.json'
    facts_path = directory / 'facts.json'
    result = run_process_group(command + ['--output', str(result_path)], cwd=cwd,
        task_id=run_id, log_path=directory/'worker.log', progress_path=directory/'progress.jsonl',
        timeout_seconds=timeout_seconds,
        extra_env={RUN_ENV:run_id, FACT_ENV:str(facts_path)})
    try:
        facts = json.loads(facts_path.read_text()) if facts_path.exists() else {}
    except (OSError, ValueError):
        facts = {}
    if not isinstance(facts, dict):
        facts = {}
    if facts.get('run_id') != run_id:
        facts = {}
    parsed = None
    try:
        parsed = json.loads(result_path.read_text())
    except (OSError, ValueError):
        pass
    valid = isinstance(parsed, dict) and parsed.get('run_id') == run_id
    worker = {**asdict(result), 'run_id':run_id, 'evidence_dir':str(directory),
              'result_identity_verified':valid, 'terminal_status':
              'timed_out' if result.timed_out else 'completed' if result.returncode == 0 and valid else 'failed'}
    # Bind only the known evidence files to this run; governance preserves
    # completed evidence without allowlisting an arbitrary runtime directory.
    manifest = {"schema_version":"delivery_supervisor_evidence_v1", "run_id":run_id,
                "market":market, "window":window, "terminal_status":worker["terminal_status"],
                "files":{}}
    for name in ("worker.log", "progress.jsonl", "facts.json", "result.json"):
        path = directory / name
        if path.is_file():
            manifest["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
    if valid and not result.timed_out and result.returncode >= 0:
        parsed['worker'] = worker
        parsed['retained_facts'] = facts
        if result.returncode != 0:
            parsed['ok'] = False
        return parsed
    return {'ok':False, 'run_id':run_id, 'market':market, 'window':window,
            'status':'timed_out' if result.timed_out else 'failed',
            'failure_reason':'worker_timeout' if result.timed_out else 'worker_failed_or_stale_result',
            'worker':worker, 'retained_facts':facts,
            'delivery_success_claimed':False, 'safe_to_retry':False}
