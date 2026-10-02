#!/usr/bin/env python3
"""Offline failure semantics gate; no provider/pipeline/delivery invocation."""
import io
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
def main():
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"),pattern="test_structured_card_258a.py")
    output=io.StringIO()
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(suite)
    ok=result.wasSuccessful() and not result.skipped and result.testsRun>=40
    print(json.dumps({"schema_version":"ai_dev_258a_structured_card_failure_v1","status":"PASS" if ok else "FAIL",
                     "tests_run":result.testsRun,"failures":[] if ok else [output.getvalue()],
                     "incident_exact_replay":"UNAVAILABLE_MISSING_ORIGINAL_INPUTS","production_mutation":"NONE"}))
    return 0 if ok else 1
if __name__=="__main__":raise SystemExit(main())
