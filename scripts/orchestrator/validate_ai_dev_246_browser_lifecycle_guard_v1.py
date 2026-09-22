#!/usr/bin/env python3
"""Offline lifecycle fault injection; no Chrome, credentials, pipeline or delivery."""
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_browser_lifecycle.py')
stream = io.StringIO()
result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
print(json.dumps({
    'schema_version': 'ai_dev_246_browser_lifecycle_guard_v1',
    'status': 'PASS' if result.wasSuccessful() else 'FAIL',
    'tests_run': result.testsRun,
    'passed': result.testsRun-len(result.errors)-len(result.failures)-len(result.skipped),
    'skipped': [(str(test), reason) for test, reason in result.skipped],
    'failures': stream.getvalue() if not result.wasSuccessful() else [],
    'live_browser_launched': False,
    'production_mutation': 'NONE',
}, ensure_ascii=False, indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
