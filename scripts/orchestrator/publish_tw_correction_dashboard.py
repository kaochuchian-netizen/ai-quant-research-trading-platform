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
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--static-root", type=Path)
    parser.add_argument("--original-html", type=Path)
    parser.add_argument("--expected-original-hash")
    parser.add_argument("--audit-root", type=Path)
    parser.add_argument("--public-base-url")
    args = parser.parse_args()
    common = dict(expected_id=args.expected_correction_id)
    if not args.publish:
        plan = prepare(args.source_dir, args.pre_open_input, args.post_close_input, **common)
        print(json.dumps({"status": "PREVIEW_ONLY", "route": plan["route"], "metrics": plan["metrics"],
                          "html_sha256": sha(plan["html"]), "notification_sent": False}, ensure_ascii=False))
        return
    if not all((args.static_root, args.original_html, args.expected_original_hash, args.audit_root, args.public_base_url)):
        parser.error("--publish requires static-root, original-html, expected-original-hash, audit-root and public-base-url")
    result = publish(args.source_dir, args.pre_open_input, args.post_close_input, **common,
                     static_root=args.static_root, original_html=args.original_html,
                     expected_original_hash=args.expected_original_hash, audit_root=args.audit_root,
                     verify_public=http_verifier(args.public_base_url))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
