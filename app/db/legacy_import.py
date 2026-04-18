"""Legacy SQLite import helpers for the database layer."""

from __future__ import annotations

import logging
import os
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .constants import DB_PATH, LEGACY_DB_PATHS, PROVIDER_1984, _secret_key

logger = logging.getLogger(__name__)


def _connect_legacy(path: Path) -> sqlite3.Connection:
    legacy_conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    legacy_conn.row_factory = sqlite3.Row
    return legacy_conn


def _resolve_legacy_path(legacy_path: str | Path) -> Path:
    path = Path(legacy_path)
    if not path.is_absolute():
        path = (Path(__file__).resolve().parents[2] / path).resolve()
    else:
        path = path.resolve()
    return path


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _insert_or_ignore(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[object, ...],
) -> bool:
    before = conn.total_changes
    conn.execute(sql, params)
    return conn.total_changes > before


def _import_marker_key(legacy_path: str | Path) -> str:
    return f"legacy_import:{os.path.normpath(str(legacy_path))}"


def _import_single_legacy_db(conn: sqlite3.Connection, legacy_path: str | Path) -> None:
    path = _resolve_legacy_path(legacy_path)
    marker_key = _import_marker_key(legacy_path)
    if conn.execute("SELECT 1 FROM config WHERE key = ?", (marker_key,)).fetchone():
        return
    if path.resolve() == Path(DB_PATH).resolve():
        return
    if not path.is_file():
        return

    try:
        with _connect_legacy(path) as legacy_conn:
            if _table_exists(legacy_conn, "config"):
                for row in legacy_conn.execute("SELECT key, value FROM config"):
                    value = row["value"]
                    if value is None or value == "":
                        continue

                    legacy_key = row["key"]
                    target_key = (
                        _secret_key(PROVIDER_1984)
                        if legacy_key == "api_key"
                        else legacy_key
                    )
                    _insert_or_ignore(
                        conn,
                        "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                        (target_key, value),
                    )

            if _table_exists(legacy_conn, "hosts"):
                for row in legacy_conn.execute("SELECT domain FROM hosts ORDER BY id"):
                    domain = (row["domain"] or "").strip().lower().rstrip(".")
                    if not domain:
                        continue

                    _insert_or_ignore(
                        conn,
                        """
                        INSERT OR IGNORE INTO dns_records (
                            provider,
                            domain,
                            record_type,
                            proxied,
                            ttl,
                            enabled
                        ) VALUES (?, ?, 'A', 0, 1, 1)
                        """,
                        (PROVIDER_1984, domain),
                    )
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (marker_key, "done"),
            )
    except sqlite3.Error as exc:
        logger.warning("Skipping legacy DB import from %s: %s", path, exc)


def import_legacy_sqlite(
    conn: sqlite3.Connection,
    legacy_paths: Iterable[str | Path] | None = None,
) -> None:
    """Import legacy data into the current schema."""

    paths = LEGACY_DB_PATHS if legacy_paths is None else legacy_paths
    for legacy_path in paths:
        _import_single_legacy_db(conn, legacy_path)
