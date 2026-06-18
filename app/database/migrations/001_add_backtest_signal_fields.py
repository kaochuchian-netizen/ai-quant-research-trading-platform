import argparse
import os
import sqlite3


DB_PATH = "data/stock_analysis.db"
TABLE_NAME = "analysis_results"


BACKTEST_SIGNAL_COLUMNS = (
    ("signal_session", "TEXT"),
    ("pipeline_type", "TEXT"),
    ("pipeline_run_id", "TEXT"),
    ("signal_time", "TEXT"),
    ("is_backtest_eligible", "INTEGER"),
    ("schema_version", "INTEGER"),
)


def get_existing_columns(conn, table_name):
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def add_column_if_missing(conn, table_name, column_name, column_definition):
    existing_columns = get_existing_columns(conn, table_name)
    if column_name in existing_columns:
        return False

    conn.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
    )
    return True


def run_migration():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        for column_name, column_definition in BACKTEST_SIGNAL_COLUMNS:
            add_column_if_missing(
                conn,
                TABLE_NAME,
                column_name,
                column_definition,
            )
        conn.commit()
    finally:
        conn.close()


def run_dry_run():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        existing_columns = get_existing_columns(conn, TABLE_NAME)
        for column_name, _column_definition in BACKTEST_SIGNAL_COLUMNS:
            status = "exists" if column_name in existing_columns else "missing"
            print(f"{column_name}: {status}")
    finally:
        conn.close()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Add backtest signal fields to analysis_results."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show backtest signal column status without modifying the database.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.dry_run:
        run_dry_run()
        return

    run_migration()


if __name__ == "__main__":
    main()
