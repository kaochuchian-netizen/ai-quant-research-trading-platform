#!/usr/bin/env python3
"""Offline AI-DEV-257 gate; no network, send or production pipeline."""
import io
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
def main():
    suite=unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_tw_observed_257.py")
    output=io.StringIO()
    result=unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    ok=result.wasSuccessful() and not result.skipped and result.testsRun >= 40
    print(json.dumps({"schema_version":"ai_dev_257_tw_observed_data_v1","status":"PASS" if ok else "FAIL", "tests_run":result.testsRun,"failures":[] if ok else [output.getvalue()],"production_mutation":"NONE"}))
    return 0 if ok else 1
if __name__ == "__main__": raise SystemExit(main())
