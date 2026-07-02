#!/usr/bin/env python3
"""Build deterministic confidence calibration artifact."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from app.calibration.calibration_builder import build_confidence_calibration_artifact, build_offline_sample_input, input_from_payload
def main() -> int:
    parser = argparse.ArgumentParser(description="Build AI-DEV-124 confidence calibration artifact."); parser.add_argument("--input"); parser.add_argument("--output"); parser.add_argument("--offline-sample", action="store_true"); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    calibration_input = None
    if args.input:
        calibration_input = input_from_payload(json.loads(Path(args.input).read_text(encoding="utf-8")))
    elif args.offline_sample:
        calibration_input = build_offline_sample_input()
    artifact = build_confidence_calibration_artifact(calibration_input).to_dict(); text = json.dumps(artifact, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    if args.output: Path(args.output).write_text(text + "\n", encoding="utf-8")
    else: sys.stdout.write(text + "\n")
    return 0
if __name__ == "__main__": raise SystemExit(main())
