#!/usr/bin/env python3
"""Offline 251D synthetic projection gate; no production ingestion or mutation."""
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_production_shadow.py")
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    ok = result.wasSuccessful() and not result.skipped and result.testsRun >= 47
    print(json.dumps({"schema_version": "ai_dev_251d_production_shadow_v1", "status": "PASS" if ok else "FAIL",
                      "tests_run": result.testsRun, "failures": [] if ok else [output.getvalue()],
                      "production_mutation": "NONE", "lifecycle_mutation": False, "input_kind": "SYNTHETIC",
                      "production_ready": False}, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
