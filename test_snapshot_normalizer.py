from app.market.shioaji_client import get_snapshots
from app.market.snapshot_normalizer import normalize_snapshots
from indicators.basic_indicator import calculate_basic_indicators


def main():
    snapshots = get_snapshots(["2330", "2317"])

    normalized = normalize_snapshots(snapshots)

    print("===== Technical Indicators =====")
    for item in normalized:
        result = calculate_basic_indicators(item)
        print(result)


if __name__ == "__main__":
    main()
