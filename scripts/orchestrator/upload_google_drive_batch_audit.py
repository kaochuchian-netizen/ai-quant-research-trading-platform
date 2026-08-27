#!/usr/bin/env python3
"""Process the batch-audit outbox without running a production batch."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime.google_drive_batch_audit import LocalProtectedOAuthProvider, process_outbox_non_blocking


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outbox", type=Path)
    parser.add_argument("--credential-file", type=Path,
                        help="Explicit protected OAuth JSON file; invalid explicit input never falls back")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    kwargs = {"outbox_root": args.outbox} if args.outbox else {}
    if args.credential_file:
        kwargs["credential_provider"] = LocalProtectedOAuthProvider(args.credential_file)
    result = process_outbox_non_blocking(**kwargs)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result.get("status") in {"PASS", "DISABLED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
