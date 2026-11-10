#!/usr/bin/env python3
"""Offline, paired peak-RSS measurement on identical temporary archive bytes.

No production files, renderer, delivery sender or snapshot writer is invoked.
The parent generates synthetic documents; fresh workers only read them using
the unmodified admission/resolver functions from each supplied checkout.
"""
import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def worker(repo, root):
    sys.path.insert(0, str(repo))
    from app.dashboard import window_snapshot_archive as archive
    reads = 0
    original = Path.read_text

    def counted(path, *args, **kwargs):
        nonlocal reads
        if path.is_relative_to(root):
            reads += 1
        return original(path, *args, **kwargs)

    Path.read_text = counted
    started = time.monotonic()
    identities = []
    for market, windows in archive.MARKET_WINDOWS.items():
        for window in windows:
            selection = archive.resolve_snapshots(root, market, window)
            revisions = archive.revisions_for_snapshot(
                root, market, window, selection.latest["effective_trading_date"])
            selected = [selection.latest, selection.previous, *revisions]
            for item in selected:
                stored = {k: v for k, v in item.items() if k != "archive_path"}
                assert not archive.admission_errors(stored)
                assert stored["snapshot_id"] == digest(
                    {k: v for k, v in stored.items() if k != "snapshot_id"})
            identities.append({
                "market": market, "window": window,
                "latest": selection.latest["snapshot_id"],
                "previous": selection.previous["snapshot_id"],
                "revisions": [item["snapshot_id"] for item in revisions],
                "payload_hashes": [digest(item["payload"]) for item in selected],
            })
    raw_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(json.dumps({"peak_rss_bytes": raw_rss if sys.platform == "darwin" else raw_rss * 1024,
                      "seconds": round(time.monotonic() - started, 4),
                      "payload_read_count": reads, "identities": identities}))


def generate(root, days, records):
    from app.dashboard import window_snapshot_archive as archive
    from app.us_stock.trading_calendar import is_us_trading_day
    dates = []
    day = date(2026, 1, 2)
    while len(dates) < days + 1:
        if is_us_trading_day(day):
            dates.append(day.isoformat())
        day += timedelta(days=1)
    entries = []
    valid_count = 0

    def put(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        path.write_bytes(data)
        entries.append((str(path.relative_to(root)), len(data), hashlib.sha256(data).hexdigest()))

    for market, windows in archive.MARKET_WINDOWS.items():
        for window in windows:
            for day in dates[:-1]:
                for revision in (1, 2):
                    stamp = f"{day}T07:00:0{revision}+08:00"
                    item = {"schema_version": archive.SCHEMA_VERSION, "market": market,
                            "window": window, "effective_trading_date": day,
                            "revision": revision, "generated_at": stamp, "admitted_at": stamp,
                            "revision_created_at": stamp, "status": "complete", "run_kind": "scheduled",
                            "runtime_provenance": "scheduled_production", "admitted": True,
                            "admission_reason": "scheduled_production_admitted",
                            "payload": {"runtime_provenance": "scheduled_production", "records": [
                                {"symbol": str(i), "text": (f"{market}-{window}-{day}-{revision}-{i}:" + "x" * 256),
                                 "factors": [1.0, 2.0, 3.0]} for i in range(records)]}}
                    item["snapshot_id"] = digest(item)
                    assert not archive.admission_errors(item)
                    put(root / market.lower() / window / day / f"revision-{revision:04d}.json", item)
                    valid_count += 1
            # An invalid newer date must not change latest/previous.
            rejected = dict(item, effective_trading_date=dates[-1], admitted=False)
            put(root / market.lower() / window / dates[-1] / "revision-0001.json", rejected)
            put(root / market.lower() / window / dates[-2] / ".frozen" / "sidecar.json", {"ignored": True})
    return {"days": days, "windows": 7, "revisions_per_date": 2,
            "records_per_payload": records, "admitted_snapshot_count": valid_count,
            "file_count": len(entries), "total_bytes": sum(v[1] for v in entries),
            "dataset_sha256": digest(sorted(entries))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--days", type=int, nargs="+", default=[30, 120])
    parser.add_argument("--records", type=int, default=256)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker.resolve(), args.archive.resolve())
        return
    if not args.baseline or not args.candidate or min(*args.days, args.records, args.repeats) < 1:
        parser.error("two checkouts and positive dataset/repetition sizes required")
    sys.path.insert(0, str(args.candidate.resolve()))
    report = {"platform": platform.platform(), "python": sys.version,
              "method": "fresh process per checkout/repetition; ru_maxrss; all 7 windows latest/previous/revisions; no mocks",
              "baseline_sha": subprocess.check_output(["git", "-C", str(args.baseline), "rev-parse", "HEAD"], text=True).strip(),
              "candidate_base_sha": subprocess.check_output(["git", "-C", str(args.candidate), "rev-parse", "HEAD"], text=True).strip(),
              "candidate_resolver_sha256": hashlib.sha256((args.candidate / "app/dashboard/window_snapshot_archive.py").read_bytes()).hexdigest(),
              "cases": []}
    for days in args.days:
        with tempfile.TemporaryDirectory(prefix="snapshot-rss-") as temp:
            root = Path(temp).resolve()
            case = generate(root, days, args.records)
            case["runs"] = []
            for repeat in range(args.repeats):
                for label, repo in (("main", args.baseline), ("pr379", args.candidate)):
                    proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", str(repo),
                                           "--archive", str(root)], capture_output=True, text=True, check=True, timeout=180)
                    case["runs"].append({"label": label, "repeat": repeat + 1, **json.loads(proc.stdout)})
            expected = case["runs"][0]["identities"]
            case["selection_admission_hash_parity"] = all(r["identities"] == expected for r in case["runs"])
            after = [(str(p.relative_to(root)), p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
                     for p in root.rglob("*.json")]
            case["immutable_file_parity"] = digest(sorted(after)) == case["dataset_sha256"]
            assert case["selection_admission_hash_parity"] and case["immutable_file_parity"]
            case["median_peak_rss_mib"] = {label: round(statistics.median(
                r["peak_rss_bytes"] for r in case["runs"] if r["label"] == label) / 1048576, 2)
                for label in ("main", "pr379")}
            report["cases"].append(case)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
