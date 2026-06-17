ADR_MAPPING = {
    "2330": "TSM",
    "2303": "UMC",
    "2412": "CHT",
    "2882": "CHWRY",
    "2881": "ESYJY",
}


def get_adr_symbol(stock_id: str):
    return ADR_MAPPING.get(str(stock_id))

