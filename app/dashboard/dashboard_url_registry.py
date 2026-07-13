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


def dashboard_url_registry() -> dict[str, str]:
    return {
        "landing": get_landing_dashboard_url(),
        "TW": get_tw_dashboard_url(),
        "US": get_us_dashboard_url(),
    }
