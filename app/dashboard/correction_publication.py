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
import tempfile

from app.dashboard.multi_market_dashboard import _atomic_copy, render_snapshot_archive_page
from app.reports.post_close_quality_gate import batch_gate
from app.reports.tw_delivery_evaluation import correction, digest

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


def prepare(source_dir: Path, pre_open_input: Path, post_close_input: Path, *, expected_id: str):
    """Verify both original envelopes, canonical results, receipt and HTML."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_id):
        raise ValueError("CORRECTION_ID_INVALID")
    source = safe_path(source_dir)
    paths = [safe_path(p) for p in (pre_open_input, post_close_input)]
    names = ("correction.json", "receipt.json", "index.html", "line.txt", "email.txt")
    blobs = {name: safe_path(source / name).read_bytes() for name in names}
    originals = [p.read_bytes() for p in paths]
    pre, post = [json.loads(b) for b in originals]
    value, receipt = json.loads(blobs["correction.json"]), json.loads(blobs["receipt.json"])
    session = value["effective_trading_date"]
    expected = correction(pre, post, session=session, revision=value["correction_revision"],
                          expected_pre_id=pre["snapshot_id"], expected_post_id=post["snapshot_id"])
    if value != expected or value["snapshot_id"] != expected_id:
        raise ValueError("CORRECTION_CANONICAL_IDENTITY")
    cards = value["payload"]["structured_review_cards"]
    gate = batch_gate(cards, market="TW", window="post_close_1500")
    if gate["status"] != "QUALIFIED":
        raise ValueError("CORRECTION_QUALITY_REJECTED")
    if (receipt.get("schema_version") != "tw_delivery_correction_validation_v1"
        or receipt.get("correction_id") != expected_id
        or receipt.get("provenance") != value["payload"]["correction_provenance"]
        or receipt.get("quality") != gate
        or receipt.get("expected_symbols") != value["payload"]["notification_universe"]
        or any(receipt.get(k) is not False for k in ("notification_sent", "database_write", "latest_write", "archive_write"))):
        raise ValueError("CORRECTION_RECEIPT_BINDING")
    for name, key in (("index.html", "html_sha256"), ("line.txt", "line_sha256"), ("email.txt", "email_sha256")):
        if sha(blobs[name]) != receipt.get(key):
            raise ValueError("CORRECTION_OUTPUT_HASH")
    page = blobs["index.html"].decode("utf-8")
    regenerated = render_snapshot_archive_page("TW", "post_close_1500", "previous", value,
                        {"available": False, "empty_state": "獨立更正版本，尚未正式發布"})
    if page != regenerated:
        raise ValueError("CORRECTION_RENDERER_MISMATCH")
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
    for old, new in substitutions.items():
        if old not in page:
            raise ValueError("CORRECTION_PRESENTATION_CONTRACT")
        page = page.replace(old, new)
    page = page.replace("<body ", f'<body data-correction-id="{expected_id}" data-correction-revision="{value["correction_revision"]}" data-correction-route="{route}" ', 1)
    html_identity(page, value)
    return {"html": page.encode(), "snapshot": value, "post": post, "route": route,
            "metrics": metrics(cards), "gate": gate, "source_hashes": {n: sha(b) for n, b in blobs.items()},
            "source_files": {**{str(source / n): b for n, b in blobs.items()}, **dict(zip(map(str, paths), originals))}}


def _write(path, data):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _record(path, value):
    _write(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode())


def _public_parent(root, parent):
    """Create only the new route directories, readable under restrictive umask."""
    for path in (root, *[root / Path(*parent.relative_to(root).parts[:i])
                         for i in range(1, len(parent.relative_to(root).parts) + 1)]):
        safe_path(path)
        try:
            path.mkdir(mode=0o755)
            path.chmod(0o755)
        except FileExistsError:
            if not path.is_dir() or path.stat().st_mode & 0o005 != 0o005:
                raise ValueError("CORRECTION_PUBLIC_DIRECTORY_MODE")


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(source_dir, pre_open_input, post_close_input, *, expected_id,
            static_root, original_html, expected_original_hash, audit_root, verify_public=None):
    """Publish only the exclusive correction URL. A failed attempt is not retried.

    verify_public is an optional bounded HTTP verifier provided by the operator;
    returning False rolls back only this attempt's own new inode. Source/latest
    are never rollback targets. Unknown/interrupted attempts require review.
    """
    plan = prepare(source_dir, pre_open_input, post_close_input, expected_id=expected_id)
    root, audit = safe_path(static_root), safe_path(audit_root)
    original = safe_path(original_html)
    repo = Path(__file__).resolve().parents[2]
    if not root.is_dir() or audit == root or root in audit.parents or audit == repo or repo in audit.parents:
        raise ValueError("CORRECTION_PRIVATE_AUDIT_REQUIRED")
    if any(audit == Path(p).parent or audit in Path(p).parents or Path(p).parent in audit.parents for p in plan["source_files"]):
        raise ValueError("CORRECTION_AUDIT_SOURCE_OVERLAP")
    target = safe_path(root / plan["route"].lstrip("/"))
    original_bytes = original.read_bytes()
    if sha(original_bytes) != expected_original_hash:
        raise ValueError("CORRECTION_ORIGINAL_HASH")
    html_identity(original_bytes.decode(), plan["post"])
    latest = safe_path(root / PREFIX / "latest/index.html")
    latest_bytes = latest.read_bytes()  # exact backup, never selected as output
    latest_body = Bodies(latest_bytes.decode()).bodies
    if len(latest_body) != 1 or latest_body[0].get("data-market") != "TW" or latest_body[0].get("data-window") != "post_close_1500":
        raise ValueError("CORRECTION_LATEST_IDENTITY")
    date.fromisoformat(latest_body[0].get("data-effective-trading-date", ""))
    for key in ("data-snapshot-id", "data-payload-hash"):
        if not re.fullmatch(r"[0-9a-f]{64}", latest_body[0].get(key, "")):
            raise ValueError("CORRECTION_LATEST_IDENTITY")
    if not latest_body[0].get("data-revision", "").isdigit():
        raise ValueError("CORRECTION_LATEST_IDENTITY")
    audit.mkdir(parents=True, exist_ok=True, mode=0o700)
    # One shared filesystem lock per public correction route, regardless of
    # caller-selected audit directory. No process termination or stale unlink.
    _public_parent(root, target.parent)
    lock = safe_path(target.parent / ".publication.lock")
    with lock.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        evidence = safe_path(audit / expected_id)
        final = evidence / "published.json"
        if target.exists():
            if final.is_file():
                saved = json.loads(final.read_text())
                if saved.get("status") == "PUBLISHED" and saved.get("target") == str(target) and saved.get("correction_id") == expected_id and saved.get("source_hashes") == plan["source_hashes"] and saved.get("metrics") == plan["metrics"] and saved.get("published_sha256") == sha(plan["html"]) == sha(target.read_bytes()):
                    return {**saved, "idempotent": True}
            raise ValueError("CORRECTION_ROUTE_COLLISION")
        if evidence.exists():
            raise ValueError("CORRECTION_PRIOR_ATTEMPT_REQUIRES_REVIEW")
        evidence.mkdir(mode=0o700)
        _write(evidence / "original.html", original_bytes)
        _write(evidence / "latest.before.html", latest_bytes)
        _write(evidence / "original.snapshot.json", json.dumps(plan["post"], ensure_ascii=False, sort_keys=True).encode())
        manifest = {"schema_version": "correction_publication_v1", "correction_id": expected_id,
                    "correction_revision": plan["snapshot"]["correction_revision"], "route": plan["route"],
                    "target": str(target), "source_hashes": plan["source_hashes"], "metrics": plan["metrics"],
                    "provenance": plan["snapshot"]["payload"]["correction_provenance"],
                    "published_sha256": sha(plan["html"]), "original_sha256": sha(original_bytes),
                    "original_path": str(original), "latest_before_sha256": sha(latest_bytes),
                    "latest_before_identity": latest_body[0], "rollback": "remove_only_verified_new_correction_route; original/latest remain untouched",
                    "notification_sent": False, "prepared_at": datetime.now(timezone.utc).isoformat()}
        _record(evidence / "prepared.json", {**manifest, "status": "PREPARED"})
        _write(evidence / "published.html", plan["html"])
        _fsync_dir(evidence)
        staged = None
        owned_inode = None
        try:
            # Existing atomic-copy primitive stages verified bytes, then hard
            # link promotion makes the public name visible atomically WITHOUT
            # overwriting any racing/unrelated file (same immutable convention
            # as production_evidence_archive).
            fd, raw = tempfile.mkstemp(prefix=".correction-", dir=target.parent)
            os.close(fd)
            staged = Path(raw)
            _atomic_copy(evidence / "published.html", staged)
            os.chmod(staged, 0o644)
            with staged.open("rb") as f:
                os.fsync(f.fileno())
            if sha(staged.read_bytes()) != manifest["published_sha256"]:
                raise ValueError("CORRECTION_STAGING_HASH")
            if original.read_bytes() != original_bytes or latest.read_bytes() != latest_bytes:
                raise ValueError("CORRECTION_ORIGINAL_OR_LATEST_CHANGED")
            if any(Path(p).read_bytes() != b for p, b in plan["source_files"].items()):
                raise ValueError("CORRECTION_SOURCE_CHANGED")
            os.link(staged, target)
            owned_inode = target.stat().st_ino
            _fsync_dir(target.parent)
            if sha(target.read_bytes()) != manifest["published_sha256"] or (verify_public and verify_public(target, plan["route"], manifest["published_sha256"]) is not True):
                raise ValueError("CORRECTION_PUBLIC_VERIFICATION")
            result = {**manifest, "status": "PUBLISHED", "published_at": datetime.now(timezone.utc).isoformat(),
                      "idempotent": False, "http_verified": verify_public is not None}
            _record(final, result)
            _fsync_dir(evidence)
            return result
        except Exception as exc:
            rolled_back = False
            if owned_inode is not None and target.exists() and not target.is_symlink() and target.stat().st_ino == owned_inode and sha(target.read_bytes()) == manifest["published_sha256"]:
                target.unlink()  # only the newly published link; bytes retained privately
                _fsync_dir(target.parent)
                rolled_back = True
            _record(evidence / "failed.json", {**manifest, "status": "ROLLED_BACK" if rolled_back else "BLOCKED",
                    "exception_type": type(exc).__name__, "rolled_back": rolled_back})
            raise
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
                staged.with_name(f".{staged.name}.ai-dev-181d.tmp").unlink(missing_ok=True)
