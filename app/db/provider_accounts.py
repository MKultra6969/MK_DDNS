"""Provider account storage helpers."""

from __future__ import annotations

from contextlib import contextmanager
import sqlite3
from collections.abc import Iterator
from typing import Any

from .core import _connect

DEFAULT_PROVIDER_ACCOUNT_NAME = "Default"


@contextmanager
def _connection(conn: sqlite3.Connection | None) -> Iterator[sqlite3.Connection]:
    if conn is not None:
        yield conn
        return

    with _connect() as owned_conn:
        yield owned_conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def provider_accounts_table_exists(conn: sqlite3.Connection | None = None) -> bool:
    with _connection(conn) as active_conn:
        return _table_exists(active_conn, "provider_accounts")


def ensure_provider_accounts_table(conn: sqlite3.Connection | None = None) -> None:
    with _connection(conn) as active_conn:
        active_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS provider_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                name TEXT NOT NULL,
                secret TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, name)
            )
            """
        )


def _provider_account_row(
    conn: sqlite3.Connection,
    provider: str,
    name: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT
            id,
            provider,
            name,
            secret,
            enabled,
            created_at
        FROM provider_accounts
        WHERE provider = ? AND name = ?
        ORDER BY id
        LIMIT 1
        """,
        (provider, name),
    ).fetchone()


def get_provider_account(
    provider: str,
    name: str = DEFAULT_PROVIDER_ACCOUNT_NAME,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    with _connection(conn) as active_conn:
        if not _table_exists(active_conn, "provider_accounts"):
            return None

        row = _provider_account_row(active_conn, provider, name)
        return dict(row) if row else None


def get_provider_account_by_id(
    account_id: int,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    with _connection(conn) as active_conn:
        if not _table_exists(active_conn, "provider_accounts"):
            return None

        row = active_conn.execute(
            """
            SELECT
                id,
                provider,
                name,
                secret,
                enabled,
                created_at
            FROM provider_accounts
            WHERE id = ?
            """,
            (account_id,),
        ).fetchone()
        return dict(row) if row else None


def list_provider_accounts(
    provider: str | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    with _connection(conn) as active_conn:
        if not _table_exists(active_conn, "provider_accounts"):
            return []

        query = """
            SELECT
                id,
                provider,
                name,
                secret,
                enabled,
                created_at
            FROM provider_accounts
        """
        params: tuple[Any, ...] = ()
        if provider:
            query += " WHERE provider = ?"
            params = (provider,)
        query += " ORDER BY provider, name, id"

        rows = active_conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def ensure_provider_account(
    provider: str,
    name: str = DEFAULT_PROVIDER_ACCOUNT_NAME,
    *,
    secret: str | None = None,
    enabled: bool = True,
    conn: sqlite3.Connection | None = None,
) -> int:
    with _connection(conn) as active_conn:
        ensure_provider_accounts_table(active_conn)
        row = _provider_account_row(active_conn, provider, name)
        if row is None:
            active_conn.execute(
                """
                INSERT INTO provider_accounts (
                    provider,
                    name,
                    secret,
                    enabled
                ) VALUES (?, ?, ?, ?)
                """,
                (provider, name, secret, int(enabled)),
            )
            row = _provider_account_row(active_conn, provider, name)
        elif secret is not None and row["secret"] in (None, ""):
            active_conn.execute(
                "UPDATE provider_accounts SET secret = ? WHERE id = ?",
                (secret, row["id"]),
            )
            row = _provider_account_row(active_conn, provider, name)

        return int(row["id"]) if row else 0


def set_provider_account_secret(
    provider: str,
    secret: str | None,
    name: str = DEFAULT_PROVIDER_ACCOUNT_NAME,
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    with _connection(conn) as active_conn:
        ensure_provider_accounts_table(active_conn)
        active_conn.execute(
            """
            INSERT INTO provider_accounts (
                provider,
                name,
                secret,
                enabled
            ) VALUES (?, ?, ?, 1)
            ON CONFLICT(provider, name) DO UPDATE SET
                secret = excluded.secret
            """,
            (provider, name, secret),
        )


def set_provider_account_enabled(
    provider: str,
    enabled: bool,
    name: str = DEFAULT_PROVIDER_ACCOUNT_NAME,
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    with _connection(conn) as active_conn:
        ensure_provider_accounts_table(active_conn)
        active_conn.execute(
            """
            INSERT INTO provider_accounts (
                provider,
                name,
                enabled
            ) VALUES (?, ?, ?)
            ON CONFLICT(provider, name) DO UPDATE SET
                enabled = excluded.enabled
            """,
            (provider, name, int(enabled)),
        )


def get_provider_account_secret(
    provider: str,
    name: str = DEFAULT_PROVIDER_ACCOUNT_NAME,
    *,
    conn: sqlite3.Connection | None = None,
) -> str | None:
    account = get_provider_account(provider, name, conn=conn)
    return account["secret"] if account else None


def sync_dns_records_provider_account_ids(
    *,
    conn: sqlite3.Connection | None = None,
    provider_account_name: str = DEFAULT_PROVIDER_ACCOUNT_NAME,
    create_missing: bool = True,
) -> int:
    with _connection(conn) as active_conn:
        if not _table_exists(active_conn, "dns_records"):
            return 0

        ensure_provider_accounts_table(active_conn)

        rows = active_conn.execute(
            """
            SELECT DISTINCT provider
            FROM dns_records
            WHERE provider IS NOT NULL AND provider != ''
            """
        ).fetchall()

        updated = 0
        for row in rows:
            provider = row["provider"]
            account = _provider_account_row(active_conn, provider, provider_account_name)
            if account is None:
                if not create_missing:
                    continue
                account_id = ensure_provider_account(
                    provider,
                    provider_account_name,
                    conn=active_conn,
                )
            else:
                account_id = int(account["id"])

            cursor = active_conn.execute(
                """
                UPDATE dns_records
                SET provider_account_id = ?
                WHERE provider = ?
                  AND (provider_account_id IS NULL OR provider_account_id = 0)
                """,
                (account_id, provider),
            )
            if cursor.rowcount and cursor.rowcount > 0:
                updated += cursor.rowcount

        return updated
