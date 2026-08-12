#!/usr/bin/env python3
"""Compatibility entry point for the active AI-DEV-193 parity contract."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.orchestrator.validate_ai_dev_193_contracts import main


if __name__ == "__main__":
    raise SystemExit(main())
