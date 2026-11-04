#!/usr/bin/env python3
"""Audit supplied immutable JSON only; stdout report, nonzero for FAIL/UNKNOWN."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.evaluation.platform_quality import check_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--receipt', action='append', type=Path, default=[])
    args = parser.parse_args()
    result = check_snapshot(json.loads(args.snapshot.read_text()), [json.loads(p.read_text()) for p in args.receipt])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
