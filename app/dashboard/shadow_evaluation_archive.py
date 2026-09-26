"""Derived immutable sidecars owned by the existing window snapshot archive."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from app.evaluation.offline_report_projection import digest
from app.evaluation.production_shadow import VERSION, source_packet, build_shadow, bind_predecessor, validate_shadow
from app.evaluation.session_calendar import CalendarError, load_calendar

def persist(snapshot_path):
    path = Path(snapshot_path)
    if path.is_symlink() or path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("SOURCE_PATH")
    snapshot = json.loads(path.read_text())
    from app.dashboard.window_snapshot_archive import snapshot_id, admission_errors
    if admission_errors(snapshot) or snapshot["snapshot_id"] != snapshot_id({k:v for k,v in snapshot.items() if k != "snapshot_id"}):
        raise ValueError("SOURCE_INTEGRITY")
    packet = source_packet(snapshot)
    try:
        calendar = load_calendar(snapshot["market"])
    except CalendarError:
        calendar = None
    identity = digest({"source": packet["source_digest"], "contract": VERSION})
    target = path.parent / ".evaluation" / (identity + ".json")
    if target.exists():
        previous = json.loads(target.read_text())
        validate_shadow(previous)
        if previous["evaluation_inputs"] != packet:
            raise ValueError("IMMUTABLE_IDENTITY_CONFLICT")
        return {"status": "IDEMPOTENT", "path": str(target), "content_hash": previous["content_hash"]}
    current = build_shadow(packet, calendar)
    predecessor = None
    corrupt = False
    # Archive date directories are bounded by retained history; inspect nearest prior
    # successful scored session, with deterministic date/revision/hash tie breaking.
    candidates = []
    if snapshot["run_kind"] == "scheduled":
        for day in sorted(path.parent.parent.iterdir(), reverse=True):
            if not day.is_dir() or not day.name < packet["review_session"]:
                continue
            for p in sorted((day / ".evaluation").glob("*.json")):
                try:
                    if p.is_symlink() or p.stat().st_size > 8 * 1024 * 1024:
                        raise ValueError("PREDECESSOR_SIZE")
                    item = json.loads(p.read_text())
                    validate_shadow(item)
                    if item["scored_predecessor_eligible"]:
                        candidates.append(item)
                except (OSError, ValueError, KeyError, TypeError):
                    corrupt = True
            if candidates or corrupt:
                break
        if candidates:
            predecessor = max(candidates, key=lambda v: (v["report_identity"]["revision"], v["content_hash"]))
    current = bind_predecessor(current, predecessor)
    if corrupt:
        current["comparison"] = {"status": "REJECTED", "predecessor_ref": None, "reason": "CORRUPTED_PREDECESSOR"}
        current["content_hash"] = digest({k:v for k,v in current.items() if k != "content_hash"})
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(current, out, ensure_ascii=False, sort_keys=True, separators=(",",":"))
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temporary, target)  # exclusive, atomic publication; never overwrite
        except FileExistsError:
            if json.loads(target.read_text()) != current:
                raise ValueError("IMMUTABLE_CONCURRENT_CONFLICT")
    finally:
        os.unlink(temporary)
    return {"status": current["status"], "path": str(target), "content_hash": current["content_hash"]}

def hook(snapshot_path):
    """Bounded worker; diagnostic errors never enter delivery decision/result."""
    try:
        result = subprocess.run([sys.executable, "-m", "app.dashboard.shadow_evaluation_archive", str(snapshot_path)],
            cwd=str(Path(__file__).resolve().parents[2]), capture_output=True, timeout=3, check=False)
        status = "WORKER_FAILED"
        if result.returncode == 0:
            value = json.loads(result.stdout)
            status = value["status"] if value.get("status") in {"BLOCKED_INPUT", "PENDING", "INSUFFICIENT_SAMPLE", "EVALUATED", "IDEMPOTENT"} else "WORKER_PROTOCOL_ERROR"
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        status = "WORKER_UNAVAILABLE"
    print(json.dumps({"event": "shadow_evaluation_worker", "status": status}), file=sys.stderr)

if __name__ == "__main__":
    try:
        print(json.dumps(persist(sys.argv[1]), sort_keys=True))
    except Exception:
        print('{"status":"SHADOW_FAILURE"}')
        raise SystemExit(1)
