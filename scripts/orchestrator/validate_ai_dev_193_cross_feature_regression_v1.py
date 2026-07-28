"""Backward-compatible direct entrypoint for the AI-DEV-193 regression gate."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.orchestrator.validate_ai_dev_193_contracts import main

raise SystemExit(main())
