"""Narrow offline validator for AI-DEV-270C; never invokes a provider."""
from __future__ import annotations

from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    contract = json.loads((ROOT / "config/governance/tw_intraday_1m_contract_v2.json").read_text(encoding="utf-8"))
    expected = {
        "schema_version": "tw_intraday_1m_contract_v2",
        "program_id": "AI-DEV-270C",
        "activation": "OFFLINE_FOUNDATION_ONLY",
        "bar_timestamp_convention": "BAR_END_TIMESTAMP_HALF_OPEN_1M",
        "provider_timestamp_decoder": "SHIOAJI_KBARS_NS_LOCAL_WALL_CLOCK_V1",
        "production_ingestion_enabled": False,
        "production_evaluation_enabled": False,
    }
    failures = [key for key, value in expected.items() if contract.get(key) != value]
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_tw_intraday_1m.py")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if failures or not result.wasSuccessful():
        print(json.dumps({"status": "FAIL", "contract_failures": failures, "test_failures": len(result.failures) + len(result.errors)}))
        return 1
    print(json.dumps({"status": "PASS", "contract": contract["schema_version"], "tests": result.testsRun}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
