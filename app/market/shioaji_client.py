from app.config.settings import settings


def classify_shioaji_error(exc):
    message = str(exc).lower()
    if "no module named" in message and "shioaji" in message:
        return "shioaji_dependency_unavailable"
    if "maintenance" in message or "maintain" in message:
        return "shioaji_maintenance"
    if "version" in message or "upgrade" in message or "update" in message:
        return "shioaji_version_or_upgrade_required"
    if "login" in message or "authentication" in message or "api_key" in message or "secret" in message:
        return "shioaji_login_failed"
    if "kbars" in message or "30" in message or "range" in message:
        return "shioaji_kbars_range_or_history_limit"
    return "shioaji_runtime_error"


class ShioajiClientError(RuntimeError):
    def __init__(self, message, classification="shioaji_runtime_error"):
        super().__init__(message)
        self.classification = classification


def get_api():
    try:
        import shioaji as sj
    except Exception as exc:
        classification = classify_shioaji_error(exc)
        raise ShioajiClientError(
            f"Shioaji import failed before market-data fetch ({classification})",
            classification=classification,
        ) from exc

    api = sj.Shioaji(simulation=True)

    try:
        api.login(
            api_key=settings.SINOPAC_API_KEY,
            secret_key=settings.SINOPAC_SECRET_KEY,
        )
    except Exception as exc:
        classification = classify_shioaji_error(exc)
        raise ShioajiClientError(
            f"Shioaji login failed before market-data fetch ({classification})",
            classification=classification,
        ) from exc
    return api


def get_snapshots(stock_ids):
    api = get_api()

    contracts = []
    for stock_id in stock_ids:
        contract = api.Contracts.Stocks[str(stock_id)]
        contracts.append(contract)

    snapshots = api.snapshots(contracts)

    return snapshots
