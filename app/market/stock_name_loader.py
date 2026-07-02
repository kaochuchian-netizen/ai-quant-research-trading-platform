import json
from functools import lru_cache
from pathlib import Path

from app.market.shioaji_client import get_api


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_STOCK_NAME_MAPS = [
    PROJECT_ROOT / "data" / "stock_name_map.json",
    PROJECT_ROOT / "data" / "stock_names.json",
    PROJECT_ROOT / "app" / "market" / "stock_name_map.json",
]


@lru_cache(maxsize=1)
def load_local_stock_name_map() -> dict[str, str]:
    names: dict[str, str] = {}
    for path in LOCAL_STOCK_NAME_MAPS:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        for stock_id, stock_name in payload.items():
            stock_id = str(stock_id).strip().zfill(4)
            stock_name = str(stock_name).strip()
            if stock_id and stock_name:
                names[stock_id] = stock_name
    return names


def resolve_stock_name(stock_id: str) -> dict[str, str | None]:
    normalized_stock_id = str(stock_id).strip().zfill(4)
    local_name = load_local_stock_name_map().get(normalized_stock_id)
    if local_name:
        return {
            "stock_id": normalized_stock_id,
            "stock_name": local_name,
            "source": "local_stock_name_map",
            "warning": None,
        }

    try:
        api = get_api()
        contract = api.Contracts.Stocks[normalized_stock_id]
        stock_name = str(getattr(contract, "name", "")).strip()
        if stock_name:
            return {
                "stock_id": normalized_stock_id,
                "stock_name": stock_name,
                "source": "shioaji_contracts",
                "warning": None,
            }
    except Exception as exc:
        classification = getattr(exc, "classification", exc.__class__.__name__)
        return {
            "stock_id": normalized_stock_id,
            "stock_name": normalized_stock_id,
            "source": "stock_id_fallback",
            "warning": str(classification),
        }

    return {
        "stock_id": normalized_stock_id,
        "stock_name": normalized_stock_id,
        "source": "stock_id_fallback",
        "warning": "stock_name_not_found",
    }


def get_stock_name(stock_id: str) -> str:
    """
    安全取得股票名稱。
    Shioaji 或本地 map 不可用時回傳股票代號，避免報告 pipeline 中斷。
    """
    return str(resolve_stock_name(stock_id)["stock_name"])
