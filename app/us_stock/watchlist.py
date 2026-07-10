"""US Google Sheet 工作表2 watchlist normalization.

Runtime code can use the same Google Sheet file as the Taiwan watchlist, while
validators and builders use deterministic local rows. US symbols are never
routed to Shioaji, TWSE, Taiwan chip, or Taiwan margin modules here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from app.us_stock.constants import DEFAULT_CURRENCY, DEFAULT_MARKET, US_SOURCE_SHEET

TRUE_VALUES = {"true", "yes", "1", "y", "enabled", "on", "是", "啟用"}
FALSE_VALUES = {"false", "no", "0", "n", "disabled", "off", "否", "停用"}

COLUMN_ALIASES = {
    "symbol": ["symbol", "ticker", "代號", "股票代號"],
    "name": ["name", "company_name", "公司名稱", "名稱"],
    "market": ["market", "市場"],
    "exchange": ["exchange", "交易所"],
    "currency": ["currency", "幣別"],
    "enabled": ["enabled", "啟用", "active"],
    "note": ["note", "notes", "備註"],
}

@dataclass(frozen=True)
class USWatchlistEntry:
    symbol: str
    name: str | None
    market: str
    exchange: str | None
    currency: str
    enabled: bool
    note: str | None
    source_sheet: str
    source_kind: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _clean(value: Any) -> str:
    return str(value or "").strip()

def parse_enabled(value: Any) -> bool:
    text = _clean(value).lower()
    if not text:
        return True
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return True

def normalize_symbol(value: Any) -> str:
    return _clean(value).upper()

def _alias_lookup(row: dict[str, Any], logical_name: str) -> Any:
    lower = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in COLUMN_ALIASES[logical_name]:
        key = alias.lower()
        if key in lower:
            return lower[key]
    return None

def normalize_us_watchlist_rows(rows: Iterable[dict[str, Any]], source_sheet: str = US_SOURCE_SHEET) -> list[dict[str, Any]]:
    seen: set[str] = set()
    entries: list[dict[str, Any]] = []
    for row in rows:
        symbol = normalize_symbol(_alias_lookup(row, "symbol"))
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        name = _clean(_alias_lookup(row, "name")) or None
        exchange = _clean(_alias_lookup(row, "exchange")) or None
        currency = (_clean(_alias_lookup(row, "currency")) or DEFAULT_CURRENCY).upper()
        note = _clean(_alias_lookup(row, "note")) or None
        enabled = parse_enabled(_alias_lookup(row, "enabled"))
        entries.append(
            USWatchlistEntry(
                symbol=symbol,
                name=name,
                market=DEFAULT_MARKET,
                exchange=exchange,
                currency=currency,
                enabled=enabled,
                note=note,
                source_sheet=source_sheet,
                source_kind="google_sheet_us_watchlist",
            ).to_dict()
        )
    return entries
