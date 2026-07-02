"""Action effectiveness analysis."""
from __future__ import annotations
from .schemas import CalibrationSample, ActionEffectivenessResult, PLATFORM_ACTIONS, mean, pct
def _vals(group: list[CalibrationSample], field: str) -> list[float]: return [v for s in group if (v := getattr(s, field)) is not None]
def _pos(vals: list[float]) -> float | None: return mean([1.0 if v > 0 else 0.0 for v in vals])
def analyze_action_effectiveness(samples: list[CalibrationSample]) -> list[ActionEffectivenessResult]:
    total = sum(1 for s in samples if s.action in PLATFORM_ACTIONS and s.action != "unknown")
    rows: list[ActionEffectivenessResult] = []; avgs: dict[str,float|None] = {}
    for action in PLATFORM_ACTIONS:
        group = [s for s in samples if s.action == action]
        hits = [1.0 if s.direction_hit else 0.0 for s in group if s.direction_hit is not None]
        r1 = _vals(group,"actual_return_1d"); r5 = _vals(group,"actual_return_5d"); r20 = _vals(group,"actual_return_20d")
        avgs[action] = mean(r20) if r20 else mean(r5) if r5 else mean(r1)
        rows.append(ActionEffectivenessResult(action, len(group), pct(mean(hits)), pct(mean(r1)), pct(mean(r5)), pct(mean(r20)), pct(_pos(r1)), pct(_pos(r5)), pct(_pos(r20)), "not_available" if not group else "insufficient_sample"))
    if total >= 20:
        bullish = mean([v for k in ("偏多加碼","偏多續抱") if (v := avgs.get(k)) is not None]); neutral = avgs.get("中性觀察"); conservative = mean([v for k in ("降低追價","保守觀望") if (v := avgs.get(k)) is not None])
        overall = "effective"
        if bullish is not None and neutral is not None and bullish < neutral - 0.005: overall = "inverted"
        elif bullish is not None and conservative is not None and bullish <= conservative: overall = "weakly_effective"
        rows = [ActionEffectivenessResult(*(tuple(r.to_dict().values())[:-1]), (overall if r.sample_size >= 5 and r.action != "unknown" else r.finding)) for r in rows]
    return rows
