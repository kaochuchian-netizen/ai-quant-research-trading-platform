#!/usr/bin/env python3
"""Preview a verified TW correction; --publish requires separate PM approval.

No latest update, batch execution or notification. Publication always uses the
fixed date/content-addressed correction route, not a caller-supplied path.
"""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.dashboard.correction_publication import prepare, publish, sha
from app.dashboard.trusted_static_root import StaticRoot, load_policy


def http_verifier(base_url):
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("CORRECTION_PUBLIC_URL_INVALID")

    def verify(target, route, expected_hash):
        url = base_url.rstrip("/") + route
        with urlopen(url, timeout=10) as response:
            return response.status == 200 and response.geturl() == url and sha(response.read()) == expected_hash
    return verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--pre-open-input", type=Path, required=True)
    parser.add_argument("--post-close-input", type=Path, required=True)
    parser.add_argument("--expected-correction-id", required=True)
    parser.add_argument("--expected-receipt-hash", required=True, help="Independently approved SHA256 of saved receipt.json")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--preflight", action="store_true", help="Read-only identity, topology, resource and route checks")
    parser.add_argument("--trusted-static-root-config", type=Path, help="Explicit reviewed logical/physical root and device/inode allowlist")
    parser.add_argument("--static-root", type=Path)
    parser.add_argument("--original-html", type=Path)
    parser.add_argument("--expected-original-hash")
    parser.add_argument("--audit-root", type=Path)
    parser.add_argument("--public-base-url")
    args = parser.parse_args()
    common = dict(expected_id=args.expected_correction_id, expected_receipt_hash=args.expected_receipt_hash)
    policy = load_policy(args.trusted_static_root_config) if args.trusted_static_root_config else None
    if policy is not None:
        if args.static_root is None:
            parser.error("trusted-static-root-config requires static-root")
        with StaticRoot(args.static_root, policy) as checked:
            checked.check()  # read-only preflight even in preview mode
    if not args.publish and not args.preflight:
        plan = prepare(args.source_dir, args.pre_open_input, args.post_close_input, **common)
        print(json.dumps({"status": "PREVIEW_ONLY", "route": plan["route"], "metrics": plan["metrics"],
                          "html_sha256": sha(plan["html"]), "notification_sent": False}, ensure_ascii=False))
        return
    if not all((args.static_root, args.original_html, args.expected_original_hash, args.audit_root)) or (args.publish and not args.public_base_url):
        parser.error("--publish requires static-root, original-html, expected-original-hash, audit-root and public-base-url")
    result = publish(args.source_dir, args.pre_open_input, args.post_close_input, **common,
                     static_root=args.static_root, original_html=args.original_html,
                     expected_original_hash=args.expected_original_hash, audit_root=args.audit_root,
                     verify_public=http_verifier(args.public_base_url) if args.publish else None, trusted_root=policy, preflight_only=args.preflight)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
