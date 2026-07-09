#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import re
import sys

PIN_RE = re.compile(r"^[0-9]{6}$")
PREFIX = "sha256:"


def hash_pin(pin: str) -> str:
    if not PIN_RE.fullmatch(pin):
        raise ValueError("PIN must be exactly 6 digits")
    return PREFIX + hashlib.sha256(pin.encode("utf-8")).hexdigest()


def verify_pin(pin: str, pin_hash: str) -> bool:
    if not PIN_RE.fullmatch(pin):
        return False
    if not pin_hash.startswith(PREFIX):
        return False
    return hmac.compare_digest(hash_pin(pin), pin_hash)


def main() -> int:
    parser = argparse.ArgumentParser(description="Hash a runtime-only 6-digit manual rerun PIN.")
    parser.add_argument("--pin", help="6-digit PIN. Prefer interactive input so shell history does not record it.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    pin = args.pin if args.pin is not None else getpass.getpass("6-digit manual rerun PIN: ")
    try:
        pin_hash = hash_pin(pin)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2 if args.pretty else None))
        return 2
    result = {
        "ok": True,
        "hash": pin_hash,
        "env_var": "STOCK_AI_MANUAL_RERUN_PIN_HASH",
        "plaintext_pin_printed": False,
        "repo_modified": False,
        "env_modified": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
