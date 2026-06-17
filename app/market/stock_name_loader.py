from app.market.shioaji_client import get_api


def get_stock_name(stock_id: str) -> str:
    """
    使用 Shioaji Contracts 取得股票名稱。
    若查不到，回傳原股票代號，避免主流程中斷。
    """
    api = get_api()

    try:
        contract = api.Contracts.Stocks[stock_id]
        return contract.name
    except Exception:
        return stock_id
