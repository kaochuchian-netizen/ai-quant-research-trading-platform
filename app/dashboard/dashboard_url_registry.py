"""Canonical Dashboard URL registry for delivery contracts.

Delivery code must use this module instead of hard-coded Dashboard routes.
The legacy four-window path is kept by the Dashboard publisher as a Taiwan
compatibility route, but it is not a formal delivery target.
"""
from __future__ import annotations

from dataclasses import dataclass


PUBLIC_DASHBOARD_BASE_URL = "http://35.201.242.167/stock-ai-dashboard"
TW_DASHBOARD_PATH = "/dashboard/tw/index.html"
US_DASHBOARD_PATH = "/dashboard/us/index.html"
LANDING_DASHBOARD_PATH = "/index.html"
LEGACY_FOUR_WINDOW_PATH_FRAGMENT = "dashboard/decision-intelligence/four-window-preview"
WINDOW_ALIASES = {
    ("TW", "prediction_review_1500"): "post_close_1500",
    ("US", "us_review_0630"): "us_post_close_review_0630",
}
WINDOWS = {
    "TW": {"pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"},
    "US": {"us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"},
}


@dataclass(frozen=True)
class DashboardRoute:
    market: str
    path: str
    url: str


def _join(path: str) -> str:
    return f"{PUBLIC_DASHBOARD_BASE_URL}{path}"


def get_tw_dashboard_url() -> str:
    """Return the canonical Taiwan Dashboard URL for LINE/Email delivery."""
    return _join(TW_DASHBOARD_PATH)


def get_us_dashboard_url() -> str:
    """Return the canonical US Dashboard URL for LINE/Email delivery."""
    return _join(US_DASHBOARD_PATH)


def get_landing_dashboard_url() -> str:
    """Return the multi-market landing page URL."""
    return _join(LANDING_DASHBOARD_PATH)


def get_dashboard_url(market: str) -> str:
    normalized = str(market or "").strip().upper()
    if normalized in {"TW", "TAIWAN", "TPE", "台股"}:
        return get_tw_dashboard_url()
    if normalized in {"US", "USA", "美股"}:
        return get_us_dashboard_url()
    raise ValueError(f"unsupported dashboard market: {market!r}")


def get_dashboard_route(market: str) -> DashboardRoute:
    normalized = str(market or "").strip().upper()
    if normalized in {"TW", "TAIWAN", "TPE", "台股"}:
        return DashboardRoute("TW", TW_DASHBOARD_PATH, get_tw_dashboard_url())
    if normalized in {"US", "USA", "美股"}:
        return DashboardRoute("US", US_DASHBOARD_PATH, get_us_dashboard_url())
    raise ValueError(f"unsupported dashboard market: {market!r}")


def is_legacy_dashboard_url(value: str | None) -> bool:
    return LEGACY_FOUR_WINDOW_PATH_FRAGMENT in str(value or "")


def normalize_delivery_dashboard_url(market: str, candidate: str | None = None) -> str:
    """Return the canonical market URL for delivery, ignoring legacy fallbacks.

    Production delivery must never emit the legacy four-window compatibility route.
    If a wrapper, environment variable, or stale artifact supplies that route, the
    current market registry wins.
    """
    canonical = get_dashboard_url(market)
    if not candidate or is_legacy_dashboard_url(candidate):
        return canonical
    if str(candidate).strip() == canonical:
        return canonical
    return canonical


def get_window_archive_path(market: str, window: str, position: str = "latest") -> str:
    normalized_market = get_dashboard_route(market).market
    normalized_window = WINDOW_ALIASES.get((normalized_market, str(window)), str(window))
    if normalized_window not in WINDOWS[normalized_market]:
        raise ValueError(f"unsupported delivery window: {normalized_market} {window!r}")
    if position not in {"latest", "previous"}:
        raise ValueError(f"unsupported archive position: {position!r}")
    return f"/dashboard/archive/{normalized_market.lower()}/{normalized_window}/{position}/index.html"


def get_window_archive_url(market: str, window: str, position: str = "latest") -> str:
    """Return the immutable canonical archive route for one delivery window."""
    return _join(get_window_archive_path(market, window, position))


def get_delivery_dashboard_url(market: str, window: str | None = None, candidate: str | None = None) -> str:
    if window:
        return get_window_archive_url(market, window, "latest")
    return normalize_delivery_dashboard_url(market, candidate)


def dashboard_url_registry() -> dict[str, str]:
    return {
        "landing": get_landing_dashboard_url(),
        "TW": get_tw_dashboard_url(),
        "US": get_us_dashboard_url(),
        **{f"{market}:{window}:latest": get_window_archive_url(market, window) for market, windows in WINDOWS.items() for window in sorted(windows)},
    }
