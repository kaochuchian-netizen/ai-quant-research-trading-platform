"""Future-only TW native feature capture. Never called by historical replay."""
import csv
import io
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from app.evaluation.production_evidence import freeze, feature, positive
from app.evaluation.session_calendar import load_calendar, session
from app.evaluation.prediction_regression_contract import aware
from app.evaluation.offline_report_projection import digest

ROOT = Path(__file__).resolve().parents[2]

def capture(card, *, root=ROOT, clock=None):
    """Observe source now, compute separate evaluation feature, then freeze now.
    Existing tactical SMA ATR and all strategy outputs remain untouched.
    """
    clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
    p = card.get("prediction_snapshot_v2") or {}
    try:
        symbol = str(card["symbol"])
        if not symbol.isdigit() or len(symbol) > 8:
            raise ValueError("SYMBOL")
        calendar = load_calendar("TW")
        day = card["trading_date"]
        h = session(calendar, "TW", day)
        path = Path(root) / "data/historical" / (symbol + "_daily.csv")
        if path.is_symlink() or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("HISTORY_SOURCE")
        raw = path.read_bytes()
        observed = clock()
        if aware(observed) >= aware(h["open_at"]):
            raise ValueError("PREDICTION_NOT_BEFORE_SESSION")
        rows = []
        for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
            if row["date"] >= day:
                continue
            r = session(calendar, "TW", row["date"])
            if aware(r["close_at"]) > aware(observed):
                raise ValueError("HISTORY_NOT_COMPLETE")
            rows.append((row["date"], positive(float(row["high"])), positive(float(row["low"])), positive(float(row["close"]))))
        rows.sort()
        if len(rows) < 15 or len({r[0] for r in rows}) != len(rows):
            raise ValueError("HISTORY_INSUFFICIENT_OR_DUPLICATE")
        trs = [max(r[1]-r[2], abs(r[1]-prev[3]), abs(r[2]-prev[3])) for prev,r in zip(rows,rows[1:])]
        atr = sum(trs[:14])/14
        for tr in trs[14:]:
            atr = (atr*13+tr)/14
        sha = hashlib.sha256(raw).hexdigest()
        available = clock()
        provenance = dict(source="canonical_historical_csv", revision=sha, source_digest=sha,
                          as_of=session(calendar,"TW",rows[-1][0])["close_at"], available_at=available)
        atr_feature = feature("atr14", atr, producer="WILDER_14_COMPLETED_POINT_IN_TIME", **provenance)
        # Reference is the native producer value observed here, never horizon-open.
        reference = feature("reference_price", positive(p["reference_price"]), source=p["prediction_identity"],
                            revision=p["method_version"], source_digest=digest(p),
                            as_of=observed, available_at=available, producer=p["method_version"])
        frozen = freeze(prediction_id=p["prediction_identity"], symbol=symbol,
                        direction={"bullish":"UP","bearish":"DOWN","neutral":"FLAT"}[p["direction_forecast"]],
                        frozen_at=clock(), reference=reference, atr=atr_feature, calendar=calendar,
                        review_session=day, producer=p["method_version"])
        return {"status":"FROZEN", "frozen":frozen}
    except (OSError, ValueError, KeyError, TypeError):
        return {"status":"BLOCKED_INPUT", "reason":"NATIVE_FROZEN_PREREQUISITE"}



def capture_and_persist(card):
    """Production call only; preserve report bytes and delivery decisions."""
    import json
    import logging
    from app.dashboard.production_evidence_archive import publish
    from app.evaluation.production_evidence import verify
    from app.evaluation.prediction_regression_contract import stamp
    try:
        native = card.get("prediction_snapshot_v2") or {}
        if not native.get("prediction_identity"):
            return
        key = digest({"prediction_id":native["prediction_identity"],"version":"production_evidence_accumulation_v1"})
        target = ROOT / "artifacts/archive/window_snapshots/tw/pre_open_0700" / card["trading_date"] / ".frozen" / (key+".json")
        if target.exists():
            verify(json.loads(target.read_text()))
            return
        value = stamp({"schema_version":"production_evidence_accumulation_v1",
                       "native_prediction_id":native["prediction_identity"],
                       "native_prediction_digest":digest(native), "capture":capture(card)})
        publish(target,value)
    except Exception:
        logging.getLogger(__name__).warning("prediction_capture: SHADOW_FAILURE")
