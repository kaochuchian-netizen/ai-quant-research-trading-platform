import os
import sqlite3


DB_PATH = "data/stock_analysis.db"


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            stock_id TEXT NOT NULL,
            stock_name TEXT,
            close_price REAL,
            technical_score REAL,
            news_score REAL,
            adr_score REAL,
            chip_score REAL,
            total_score REAL,
            rating TEXT,
            action TEXT,
            strategy TEXT,
            report_text TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()
    conn.close()
