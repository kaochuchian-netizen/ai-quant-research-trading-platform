import shioaji as sj

from app.config.settings import settings


def get_api():
    api = sj.Shioaji(simulation=True)

    api.login(
    api_key=settings.SINOPAC_API_KEY,
    secret_key=settings.SINOPAC_SECRET_KEY,
    )
    return api


def get_snapshots(stock_ids):
    api = get_api()

    contracts = []
    for stock_id in stock_ids:
        contract = api.Contracts.Stocks[str(stock_id)]
        contracts.append(contract)

    snapshots = api.snapshots(contracts)

    return snapshots
