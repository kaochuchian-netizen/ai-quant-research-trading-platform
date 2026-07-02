"""High/low forecast error diagnostics."""
from __future__ import annotations
from .schemas import CalibrationSample, HighLowErrorResult, mean, median, pct
def analyze_high_low_error(samples: list[CalibrationSample]) -> HighLowErrorResult:
    usable = [s for s in samples if s.predicted_high is not None and s.predicted_low is not None and s.actual_high not in (None,0) and s.actual_low not in (None,0)]
    if not usable: return HighLowErrorResult(0, None, None, None, None, None, None, None, None, None, None, None, None, "not_available")
    high_errors = [abs(s.predicted_high - s.actual_high) / s.actual_high for s in usable]  # type: ignore[operator]
    low_errors = [abs(s.predicted_low - s.actual_low) / s.actual_low for s in usable]  # type: ignore[operator]
    high_bias = [(s.predicted_high - s.actual_high) / s.actual_high for s in usable]  # type: ignore[operator]
    low_bias = [(s.predicted_low - s.actual_low) / s.actual_low for s in usable]  # type: ignore[operator]
    high_over = mean([1.0 if v > 0 else 0.0 for v in high_bias]); low_over = mean([1.0 if v > 0 else 0.0 for v in low_bias])
    range_bias = [(s.predicted_high - s.predicted_low) - (s.actual_high - s.actual_low) for s in usable]  # type: ignore[operator]
    wide = mean([1.0 if v > 0 else 0.0 for v in range_bias]); narrow = mean([1.0 if v < 0 else 0.0 for v in range_bias])
    finding = "insufficient_sample" if len(usable) < 5 else "well_calibrated_range"
    if len(usable) >= 5:
        if mean(high_bias) is not None and mean(high_bias) > 0.02: finding = "high_biased_overestimate"
        elif mean(high_bias) is not None and mean(high_bias) < -0.02: finding = "high_biased_underestimate"
        elif mean(low_bias) is not None and mean(low_bias) > 0.02: finding = "low_biased_overestimate"
        elif mean(low_bias) is not None and mean(low_bias) < -0.02: finding = "low_biased_underestimate"
        elif wide is not None and wide >= 0.70: finding = "range_too_wide"
        elif narrow is not None and narrow >= 0.70: finding = "range_too_narrow"
    return HighLowErrorResult(len(usable), pct(mean(high_errors)), pct(mean(low_errors)), pct(median(high_errors)), pct(median(low_errors)), pct(mean(high_bias)), pct(mean(low_bias)), pct(high_over), pct(1-high_over if high_over is not None else None), pct(low_over), pct(1-low_over if low_over is not None else None), pct(wide), pct(narrow), finding)
