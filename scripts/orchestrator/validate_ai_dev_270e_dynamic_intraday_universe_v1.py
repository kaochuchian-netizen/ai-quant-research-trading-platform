"""Offline gate for AI-DEV-270E dynamic 07:00 universe binding."""
from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> int:
    contract = json.loads((ROOT / "config/governance/tw_intraday_dynamic_universe_v1.json").read_text())
    expected = {"schema_version": "tw_intraday_session_universe_v1", "program_id": "AI-DEV-270E", "market": "TW", "runtime_activation": "OFF", "production_archive_write_enabled": False, "production_evaluation_enabled": False}
    failures = [key for key, value in expected.items() if contract.get(key) != value]
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_tw_intraday_session_universe.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(json.dumps({"status": "PASS" if not failures and result.wasSuccessful() else "FAIL", "contract_failures": failures, "tests": result.testsRun}))
    return 0 if not failures and result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
