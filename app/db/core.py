import os
import sqlite3

from .constants import DB_PATH
from .legacy_import import import_legacy_sqlite


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs("data", exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dns_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                domain TEXT NOT NULL,
                zone_id TEXT,
                zone_name TEXT,
                record_name TEXT,
                record_type TEXT NOT NULL DEFAULT 'A',
                proxied INTEGER NOT NULL DEFAULT 0,
                ttl INTEGER NOT NULL DEFAULT 1,
                provider_record_id TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, domain)
            )
            """
        )

        import_legacy_sqlite(conn)
