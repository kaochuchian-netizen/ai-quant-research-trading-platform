"""Regression coverage for bounded archive reads and latest-selection parity."""
import json
from pathlib import Path
from unittest.mock import patch

from app.dashboard import window_snapshot_archive as archive


def _put(root: Path, market: str, window: str, day: str, revision: int, *, admitted=True):
    path = root / market.lower() / window / day / f"revision-{revision:04d}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "market": market, "window": window, "effective_trading_date": day,
        "revision": revision, "admitted_at": f"{day}T10:00:00",
        "snapshot_id": f"{market}-{window}-{day}-{revision}",
        "payload": {"data": "x" * 4096},
        "admitted": admitted,
    }), encoding="utf-8")
    return path


def test_resolver_only_opens_selected_market_window_and_latest_two_dates(tmp_path):
    root = tmp_path / "archive"
    window = "pre_open_0700"
    for day in ("2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"):
        _put(root, "TW", window, day, 1)
    _put(root, "TW", window, "2026-11-06", 2)
    _put(root, "US", "us_pre_market_2000", "2026-11-06", 1)
    with patch.object(archive, "admission_errors", side_effect=lambda item: [] if item.get("admitted") else ["not_admitted"]):
        selected = archive.resolve_snapshots(root, "TW", window)
    assert selected.latest["snapshot_id"] == "TW-pre_open_0700-2026-11-06-2"
    assert selected.previous["effective_trading_date"] == "2026-11-05"
    assert selected.latest["payload"]["data"] == "x" * 4096


def test_invalid_newest_date_falls_back_to_two_admitted_dates(tmp_path):
    root = tmp_path / "archive"
    window = "pre_open_0700"
    _put(root, "TW", window, "2026-11-06", 1, admitted=False)
    _put(root, "TW", window, "2026-11-05", 1)
    _put(root, "TW", window, "2026-11-04", 1)
    with patch.object(archive, "admission_errors", side_effect=lambda item: [] if item.get("admitted") else ["not_admitted"]):
        selected = archive.resolve_snapshots(root, "TW", window)
    assert selected.latest["effective_trading_date"] == "2026-11-05"
    assert selected.previous["effective_trading_date"] == "2026-11-04"


def test_revision_loader_does_not_include_other_dates(tmp_path):
    root = tmp_path / "archive"
    _put(root, "TW", "pre_open_0700", "2026-11-06", 1)
    _put(root, "TW", "pre_open_0700", "2026-11-06", 2)
    _put(root, "TW", "pre_open_0700", "2026-11-05", 1)
    with patch.object(archive, "admission_errors", return_value=[]):
        revisions = archive.revisions_for_snapshot(root, "TW", "pre_open_0700", "2026-11-06")
    assert [item["revision"] for item in revisions] == [1, 2]


def test_archive_payload_not_retained_in_global_cache(tmp_path):
    root = tmp_path / "archive"
    _put(root, "TW", "pre_open_0700", "2026-11-06", 1)
    with patch.object(archive, "admission_errors", return_value=[]):
        archive.resolve_snapshots(root, "TW", "pre_open_0700")
    assert not hasattr(archive, "_ADMITTED_SNAPSHOT_CACHE")

def test_large_archive_does_not_read_unrelated_payloads(tmp_path):
    """Regression: a single route must not deserialize the entire archive."""
    from datetime import date, timedelta

    root = tmp_path / "archive"
    target = "pre_open_0700"
    start = date(2026, 1, 1)
    for offset in range(300):
        day = (start + timedelta(days=offset)).isoformat()
        _put(root, "TW", target, day, 1)
        _put(root, "US", "us_pre_market_2000", day, 1)

    original = Path.read_text
    opened = []

    def tracked_read(path, *args, **kwargs):
        opened.append(str(path))
        return original(path, *args, **kwargs)

    with patch.object(archive, "admission_errors", return_value=[]), patch.object(Path, "read_text", tracked_read):
        selected = archive.resolve_snapshots(root, "TW", target)
    assert selected.latest is not None
    assert selected.previous is not None
    assert len(opened) == 2, f"Unexpected full-archive payload reads: {len(opened)}"
    assert all("/tw/pre_open_0700/" in path for path in opened)
