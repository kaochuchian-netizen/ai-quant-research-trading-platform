"""Rating effectiveness analysis."""
from __future__ import annotations
from .schemas import CalibrationSample, RatingEffectivenessResult, RATINGS, mean, median, pct
def _rates(samples: list[CalibrationSample], field: str) -> list[float]: return [v for s in samples if (v := getattr(s, field)) is not None]
def _pos(vals: list[float]) -> float | None: return mean([1.0 if v > 0 else 0.0 for v in vals])
def analyze_rating_effectiveness(samples: list[CalibrationSample]) -> list[RatingEffectivenessResult]:
    total = sum(1 for s in samples if s.rating in RATINGS and s.rating != "unknown")
    rows: list[RatingEffectivenessResult] = []
    avgs: dict[str,float|None] = {}
    for rating in RATINGS:
        group = [s for s in samples if s.rating == rating]
        hits = [1.0 if s.direction_hit else 0.0 for s in group if s.direction_hit is not None]
        r1 = _rates(group, "actual_return_1d"); r5 = _rates(group, "actual_return_5d"); r20 = _rates(group, "actual_return_20d")
        avgs[rating] = mean(r20) if r20 else mean(r5) if r5 else mean(r1)
        finding = "not_available" if not group else "insufficient_sample"
        rows.append(RatingEffectivenessResult(rating, len(group), pct(mean(hits)), pct(mean(r1)), pct(mean(r5)), pct(mean(r20)), pct(median(r1)), pct(median(r5)), pct(median(r20)), pct(_pos(r1)), pct(_pos(r5)), pct(_pos(r20)), finding))
    if total >= 20:
        bullish = mean([v for k in ("A","B") if (v := avgs.get(k)) is not None]); neutral = avgs.get("C"); defensive = mean([v for k in ("D","E") if (v := avgs.get(k)) is not None])
        overall = "effective"
        if bullish is not None and neutral is not None and bullish < neutral - 0.005: overall = "inverted"
        elif bullish is not None and defensive is not None and bullish <= defensive: overall = "weakly_effective"
        rows = [RatingEffectivenessResult(*(tuple(r.to_dict().values())[:-1]), (overall if r.sample_size >= 5 and r.rating != "unknown" else r.finding)) for r in rows]
    return rows
