"""Explicit TW correction publication; never resolve or replace latest.

Inputs remain immutable. Only publication labels/route metadata change in the
verified HTML. Private durable evidence is required before exclusive atomic
publication. No transport, database, acquisition or batch entrypoints.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
import fcntl
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import stat
import uuid

from app.dashboard.multi_market_dashboard import _atomic_copy
from app.dashboard.trusted_static_root import StaticRoot, read_at, stat_at
from app.reports.tw_delivery_evaluation import digest
from app.dashboard.verified_correction import verify_receipt_pin, verify_existing

PREFIX = "dashboard/archive/tw/post_close_1500"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(path: Path) -> Path:
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("CORRECTION_SYMLINK")
    return path.resolve()


class Bodies(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.bodies = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.bodies.append(dict(attrs))


def html_identity(page, snapshot):
    bodies = Bodies(page).bodies
    expected = {"data-market": "TW", "data-window": "post_close_1500",
                "data-effective-trading-date": snapshot["effective_trading_date"],
                "data-snapshot-id": snapshot["snapshot_id"], "data-revision": str(snapshot["revision"]),
                "data-payload-hash": digest(snapshot["payload"])}
    if len(bodies) != 1 or any(bodies[0].get(k) != v for k, v in expected.items()):
        raise ValueError("CORRECTION_HTML_IDENTITY")


def metrics(cards):
    return {part: dict(Counter(c["delivery_prediction_evaluation_v1"][part]["result"] for c in cards))
            for part in ("direction", "range")}


def prepare(source_dir: Path, pre_open_input: Path, post_close_input: Path, *, expected_id: str, expected_receipt_hash=None):
    """Verify both original envelopes, canonical results, receipt and HTML."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_id):
        raise ValueError("CORRECTION_ID_INVALID")
    source = safe_path(source_dir)
    paths = [safe_path(p) for p in (pre_open_input, post_close_input)]
    names = ("correction.json", "receipt.json", "index.html", "line.txt", "email.txt")
    blobs = {name: safe_path(source / name).read_bytes() for name in names}
    verify_receipt_pin(blobs["receipt.json"], expected_receipt_hash)
    originals = [p.read_bytes() for p in paths]
    pre, post = [json.loads(b) for b in originals]
    value, receipt = json.loads(blobs["correction.json"]), json.loads(blobs["receipt.json"])
    session = value["effective_trading_date"]
    gate = verify_existing(pre, post, value, receipt, expected_id)
    cards = value["payload"]["structured_review_cards"]
    for name, key in (("index.html", "html_sha256"), ("line.txt", "line_sha256"), ("email.txt", "email_sha256")):
        if sha(blobs[name]) != receipt.get(key):
            raise ValueError("CORRECTION_OUTPUT_HASH")
    page = blobs["index.html"].decode("utf-8")
    html_identity(page, value)
    route = f"/{PREFIX}/{session}/corrections/{expected_id}/index.html"
    # Strict, presentation-only replacements. Never rebuild individual cards or
    # change predictions/evaluations to manufacture publication eligibility.
    substitutions = {
        "隔離更正預覽（未發布）": f"{session} 15:00 更正報告",
        "隔離驗證版本，未正式發布、未發送通知。原始報告完整保留。": "本頁為獨立更正報告。原始報告完整保留；本次發布未發送通知。",
        "獨立更正版本，尚未正式發布": "獨立更正版本；原始報告完整保留",
        f"{session} 15:00 更正報告（隔離驗證，未發布）": f"{session} 15:00 更正報告",
        f"Source Route：/{PREFIX}/latest/index.html": f"Source Route：{route}",
        "本頁只使用 resolver 選出的 immutable snapshot payload；不讀取全域 latest runtime。": "本頁使用已驗證的 frozen 更正證據；不改寫原始 snapshot 或 latest。",
    }
    protected = lambda text: [re.findall(pattern, text, re.S) for pattern in
        (r'<article\b.*?</article>', r'<div class="post-close-overview".*?</div>')]
    saved_primary = protected(page)
    for old, new in substitutions.items():
        if old not in page:
            raise ValueError("CORRECTION_PRESENTATION_CONTRACT")
        page = page.replace(old, new)
    page = page.replace("<body ", f'<body data-correction-id="{expected_id}" data-correction-revision="{value["correction_revision"]}" data-correction-route="{route}" ', 1)
    html_identity(page, value)
    if protected(page) != saved_primary:
        raise ValueError("CORRECTION_PRESENTATION_CHANGED_RESULTS")
    return {"html": page.encode(), "snapshot": value, "post": post, "route": route,
            "metrics": metrics(cards), "gate": gate,
            "verification_mode": "VERIFIED_EXISTING_NO_REEVALUATION",
            "receipt_sha256": expected_receipt_hash,
            "input_hashes": {str(p):sha(b) for p,b in zip(paths,originals)},
            "presentation_transform": {"version":"correction_public_label_v1", "input_sha256":sha(blobs["index.html"]), "output_sha256":sha(page.encode())}, "source_hashes": {n: sha(b) for n, b in blobs.items()},
            "source_files": {**{str(source / n): b for n, b in blobs.items()}, **dict(zip(map(str, paths), originals))}}


def _write(path, data):
    with path.open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _record(path, value):
    _write(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode())
    _fsync_dir(path.parent)


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(source_dir, pre_open_input, post_close_input, *, expected_id,
            static_root, original_html, expected_original_hash, audit_root, verify_public=None, trusted_root=None, expected_receipt_hash=None, preflight_only=False):
    """Publish only the exclusive correction URL. A failed attempt is not retried.

    verify_public is an optional bounded HTTP verifier provided by the operator;
    returning False rolls back only this attempt's own new inode. Source/latest
    are never rollback targets. Unknown/interrupted attempts require review.
    """
    if trusted_root is None:
        safe_path(static_root)  # default remains strict: no symlink anywhere
    with StaticRoot(static_root, trusted_root) as public:
        return _publish(source_dir, pre_open_input, post_close_input, expected_id=expected_id,
                        public=public, original_html=original_html, expected_original_hash=expected_original_hash,
                        audit_root=audit_root, verify_public=verify_public, expected_receipt_hash=expected_receipt_hash, preflight_only=preflight_only)


def _publish(source_dir, pre_open_input, post_close_input, *, expected_id, public,
             original_html, expected_original_hash, audit_root, verify_public, expected_receipt_hash, preflight_only=False):
    plan = prepare(source_dir, pre_open_input, post_close_input, expected_id=expected_id, expected_receipt_hash=expected_receipt_hash)
    root, audit = public.physical, safe_path(audit_root)
    original_relative = public.relative(original_html)
    original = root / original_relative if original_relative else safe_path(original_html)
    def read_original():
        return public.read(original_relative) if original_relative else original.read_bytes()
    repo = Path(__file__).resolve().parents[2]
    if not root.is_dir() or audit == root or root in audit.parents or audit == repo or repo in audit.parents:
        raise ValueError("CORRECTION_PRIVATE_AUDIT_REQUIRED")
    if any(audit == Path(p).parent or audit in Path(p).parents or Path(p).parent in audit.parents for p in plan["source_files"]):
        raise ValueError("CORRECTION_AUDIT_SOURCE_OVERLAP")
    if audit.exists() and (not audit.is_dir() or audit.stat().st_uid != os.geteuid() or audit.stat().st_mode & 0o077):
        raise ValueError("CORRECTION_PRIVATE_AUDIT_PERMISSIONS")
    target = root / plan["route"].lstrip("/")
    original_bytes = read_original()
    if sha(original_bytes) != expected_original_hash:
        raise ValueError("CORRECTION_ORIGINAL_HASH")
    html_identity(original_bytes.decode(), plan["post"])
    latest_relative = PREFIX + "/latest/index.html"
    latest_bytes = public.read(latest_relative)  # exact backup, never selected as output
    latest_body = Bodies(latest_bytes.decode()).bodies
    if len(latest_body) != 1 or latest_body[0].get("data-market") != "TW" or latest_body[0].get("data-window") != "post_close_1500":
        raise ValueError("CORRECTION_LATEST_IDENTITY")
    date.fromisoformat(latest_body[0].get("data-effective-trading-date", ""))
    for key in ("data-snapshot-id", "data-payload-hash"):
        if not re.fullmatch(r"[0-9a-f]{64}", latest_body[0].get(key, "")):
            raise ValueError("CORRECTION_LATEST_IDENTITY")
    if not latest_body[0].get("data-revision", "").isdigit():
        raise ValueError("CORRECTION_LATEST_IDENTITY")
    # Read-only resource gate. It never probes permission with a write.
    resource = {}
    backup_bytes = len(original_bytes) + len(latest_bytes) + len(json.dumps(plan["post"]).encode())
    for label, destination, required in (("backup", audit, backup_bytes + 3 * len(plan["html"]) + 1048576),
                                          ("public", target.parent, 2 * len(plan["html"]) + 1048576)):
        destination = safe_path(destination)
        ancestor = destination
        while not ancestor.exists():
            ancestor = ancestor.parent
        if not ancestor.is_dir() or not os.access(ancestor, os.W_OK | os.X_OK):
            raise ValueError("CORRECTION_PERMISSION_" + label.upper())
        if label == "public":
            relative = ancestor.relative_to(root).as_posix()
            if relative != ".":
                public.directory(relative)
        fs = os.statvfs(ancestor)
        if fs.f_bavail * fs.f_frsize < required or (fs.f_favail >= 0 and fs.f_favail < 32):
            raise ValueError("CORRECTION_SPACE_" + label.upper())
        resource[label] = {"nearest_existing_parent": str(ancestor), "device": ancestor.stat().st_dev,
                           "available_bytes": fs.f_bavail * fs.f_frsize, "required_bytes": required}
    public.check()
    if preflight_only:
        # Existing attempts need receipt/inode verification under the publication
        # lock; preflight cannot certify recovery or idempotency without it.
        if target.exists() or (audit / expected_id).exists():
            raise ValueError("CORRECTION_EXISTING_ATTEMPT_REQUIRES_REVIEW")
        return {"status": "READ_ONLY_PREFLIGHT", "route": plan["route"], "resources": resource,
                "metrics": plan["metrics"], "receipt_sha256": expected_receipt_hash,
                "http_verified": False, "production_publication": "PENDING"}
    audit.mkdir(parents=True, exist_ok=True, mode=0o700)
    # One shared filesystem lock per public correction route, regardless of
    # caller-selected audit directory. No process termination or stale unlink.
    parent_fd = public.directory(target.parent.relative_to(root).as_posix(), create=True)
    public.check()
    lock_fd = os.open('.publication.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent_fd)
    with os.fdopen(lock_fd, 'a') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('CORRECTION_NONREGULAR_LOCK')
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        evidence = safe_path(audit / expected_id)
        final = evidence / "published.json"
        if stat_at(parent_fd, target.name) is not None:
            if final.is_file() and not (evidence / "failed.json").exists() and (evidence / "promoted.json").is_file():
                saved = json.loads(final.read_text())
                if saved.get("status") == "PUBLISHED" and saved.get("target") == str(target) and saved.get("correction_id") == expected_id and saved.get("source_hashes") == plan["source_hashes"] and saved.get("input_hashes") == plan["input_hashes"] and saved.get("metrics") == plan["metrics"] and saved.get("published_sha256") == sha(plan["html"]) == sha(read_at(parent_fd, target.name)):
                    promoted = json.loads((evidence / "promoted.json").read_text())
                    current = stat_at(parent_fd, target.name)
                    if promoted.get("owned_inode") != [current.st_dev, current.st_ino] or promoted.get("published_sha256") != saved["published_sha256"]:
                        raise ValueError("CORRECTION_PRIOR_ATTEMPT_IDENTITY")
                    if verify_public and (saved.get("http_verified") is not True or verify_public(target, plan["route"], saved["published_sha256"]) is not True):
                        raise ValueError("CORRECTION_PUBLIC_VERIFICATION")
                    public.check()
                    after = stat_at(parent_fd, target.name)
                    if after is None or (after.st_dev, after.st_ino) != (current.st_dev, current.st_ino) or sha(read_at(parent_fd, target.name)) != saved["published_sha256"]:
                        raise ValueError("CORRECTION_PUBLIC_VERIFICATION")
                    return {**saved, "idempotent": True}
            raise ValueError("CORRECTION_ROUTE_COLLISION")
        if evidence.exists():
            raise ValueError("CORRECTION_PRIOR_ATTEMPT_REQUIRES_REVIEW")
        evidence.mkdir(mode=0o700)
        _fsync_dir(audit)
        _write(evidence / "original.html", original_bytes)
        _write(evidence / "latest.before.html", latest_bytes)
        _write(evidence / "original.snapshot.json", json.dumps(plan["post"], ensure_ascii=False, sort_keys=True).encode())
        manifest = {"schema_version": "correction_publication_v1", "correction_id": expected_id,
                    "correction_revision": plan["snapshot"]["correction_revision"], "route": plan["route"],
                    "root_trust": {"logical": str(public.logical), "physical": str(root), "directories": public.pins.copy(), "alias": public.alias_pin},
                    "target": str(target), "source_hashes": plan["source_hashes"], "metrics": plan["metrics"],
                    "receipt_sha256": expected_receipt_hash, "input_hashes": plan["input_hashes"], "presentation_transform": plan["presentation_transform"],
                    "provenance": plan["snapshot"]["payload"]["correction_provenance"],
                    "published_sha256": sha(plan["html"]), "original_sha256": sha(original_bytes),
                    "original_path": str(original), "latest_before_sha256": sha(latest_bytes),
                    "latest_before_identity": latest_body[0], "rollback": "remove_only_verified_new_correction_route; original/latest remain untouched",
                    "notification_sent": False, "prepared_at": datetime.now(timezone.utc).isoformat()}
        _record(evidence / "prepared.json", {**manifest, "status": "PREPARED"})
        _write(evidence / "published.html", plan["html"])
        _fsync_dir(evidence)
        staged_name = None
        staged_inode = None
        private_staged = evidence / ".candidate.html"
        owned_inode = None
        try:
            # Keep existing copy validation in the private staging area. All
            # public writes use pinned dirfds, so a pathname swap cannot redirect
            # staging, promotion or rollback into an untrusted directory.
            _atomic_copy(evidence / "published.html", private_staged)
            data = private_staged.read_bytes()
            if sha(data) != manifest["published_sha256"]:
                raise ValueError("CORRECTION_STAGING_HASH")
            public.check()
            staged_name = ".correction-" + uuid.uuid4().hex
            fd = os.open(staged_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
            with os.fdopen(fd, 'wb') as stream:
                # Keep the inode allocated through promotion/rollback/cleanup.
                # Otherwise an unlink/recreate may reuse st_ino on Linux and
                # turn an identity-only cleanup check into a foreign deletion.
                public.fds.append(os.dup(stream.fileno()))
                st = os.fstat(stream.fileno())
                staged_inode = (st.st_dev, st.st_ino)
                stream.write(data)
                os.fchmod(stream.fileno(), 0o644)
                stream.flush()
                os.fsync(stream.fileno())
                st = os.fstat(stream.fileno())
                staged_inode = (st.st_dev, st.st_ino)
            if read_original() != original_bytes or public.read(latest_relative) != latest_bytes:
                raise ValueError("CORRECTION_ORIGINAL_OR_LATEST_CHANGED")
            if any(Path(p).read_bytes() != b for p, b in plan["source_files"].items()):
                raise ValueError("CORRECTION_SOURCE_CHANGED")
            public.check()
            st = stat_at(parent_fd, staged_name)
            if st is None or (st.st_dev, st.st_ino) != staged_inode or sha(read_at(parent_fd, staged_name)) != manifest["published_sha256"]:
                raise ValueError("CORRECTION_STAGING_IDENTITY")
            _record(evidence / "staged.json", {**manifest, "status": "STAGED", "owned_inode": staged_inode})
            os.link(staged_name, target.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
            owned_inode = staged_inode
            os.fsync(parent_fd)
            _record(evidence / "promoted.json", {**manifest, "status": "PUBLICATION_PENDING_HTTP", "owned_inode": owned_inode})
            public.check()
            st = stat_at(parent_fd, target.name)
            if st is None or (st.st_dev, st.st_ino) != owned_inode or sha(read_at(parent_fd, target.name)) != manifest["published_sha256"] or (verify_public and verify_public(target, plan["route"], manifest["published_sha256"]) is not True):
                raise ValueError("CORRECTION_PUBLIC_VERIFICATION")
            public.check()
            after = stat_at(parent_fd, target.name)
            if after is None or (after.st_dev, after.st_ino) != owned_inode or sha(read_at(parent_fd, target.name)) != manifest["published_sha256"]:
                raise ValueError("CORRECTION_PUBLIC_VERIFICATION")
            if read_original() != original_bytes or public.read(latest_relative) != latest_bytes:
                raise ValueError("CORRECTION_ORIGINAL_OR_LATEST_CHANGED")
            if any(safe_path(Path(p)).read_bytes() != b for p, b in plan["source_files"].items()):
                raise ValueError("CORRECTION_SOURCE_CHANGED")
            result = {**manifest, "status": "PUBLISHED", "published_at": datetime.now(timezone.utc).isoformat(),
                      "idempotent": False, "http_verified": verify_public is not None}
            _record(final, result)
            _fsync_dir(evidence)
            return result
        except Exception as exc:
            rolled_back = False
            if owned_inode is not None:
                try:
                    st = stat_at(parent_fd, target.name)
                    if st is not None and (st.st_dev, st.st_ino) == owned_inode and sha(read_at(parent_fd, target.name)) == manifest["published_sha256"]:
                        os.unlink(target.name, dir_fd=parent_fd)
                        os.fsync(parent_fd)
                        rolled_back = True
                except (OSError, ValueError):
                    pass  # replaced/symlink target is not ours to remove
            _record(evidence / "failed.json", {**manifest, "status": "ROLLED_BACK" if rolled_back else "BLOCKED",
                    "exception_type": type(exc).__name__, "rolled_back": rolled_back})
            raise
        finally:
            if staged_name is not None:
                try:
                    st = stat_at(parent_fd, staged_name)
                    if st is not None and staged_inode == (st.st_dev, st.st_ino):
                        os.unlink(staged_name, dir_fd=parent_fd)
                except (FileNotFoundError, ValueError):
                    pass
            private_staged.unlink(missing_ok=True)
            private_staged.with_name(f".{private_staged.name}.ai-dev-181d.tmp").unlink(missing_ok=True)
