import os
import sqlite3

from .constants import DB_PATH, PROVIDER_1984, _secret_key
from .legacy_import import import_legacy_sqlite


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def _config_secret(conn: sqlite3.Connection, provider: str) -> str | None:
    row = conn.execute(
        "SELECT value FROM config WHERE key = ?",
        (_secret_key(provider),),
    ).fetchone()
    if row is not None:
        return row["value"]

    if provider == PROVIDER_1984:
        legacy_row = conn.execute(
            "SELECT value FROM config WHERE key = ?",
            ("api_key",),
        ).fetchone()
        if legacy_row is not None:
            return legacy_row["value"]

    return None


def _configured_providers(conn: sqlite3.Connection) -> set[str]:
    providers: set[str] = set()

    for row in conn.execute(
        "SELECT key FROM config WHERE key LIKE 'provider:%:secret'",
    ).fetchall():
        key = row["key"]
        if key.startswith("provider:") and key.endswith(":secret"):
            provider = key[len("provider:") : -len(":secret")]
            if provider:
                providers.add(provider)

    if conn.execute("SELECT 1 FROM config WHERE key = ?", ("api_key",)).fetchone():
        providers.add(PROVIDER_1984)

    for row in conn.execute(
        """
        SELECT DISTINCT provider
        FROM dns_records
        WHERE provider IS NOT NULL AND provider != ''
        """
    ).fetchall():
        providers.add(row["provider"])

    return providers


def _ensure_dns_records_provider_account_id(conn: sqlite3.Connection) -> None:
    if not _column_exists(conn, "dns_records", "provider_account_id"):
        conn.execute("ALTER TABLE dns_records ADD COLUMN provider_account_id INTEGER")


def _ensure_dns_records_provider_account_triggers(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS dns_records_assign_provider_account_id_insert
        AFTER INSERT ON dns_records
        FOR EACH ROW
        WHEN NEW.provider_account_id IS NULL OR NEW.provider_account_id = 0
        BEGIN
            INSERT OR IGNORE INTO provider_accounts (provider, name, enabled)
            VALUES (NEW.provider, 'Default', 1);

            UPDATE dns_records
            SET provider_account_id = (
                SELECT id
                FROM provider_accounts
                WHERE provider = NEW.provider
                  AND name = 'Default'
                ORDER BY id
                LIMIT 1
            )
            WHERE id = NEW.id;
        END
        """
    )
    conn.execute(
        """
        CREATE TRIGGER IF NOT EXISTS dns_records_assign_provider_account_id_update
        AFTER UPDATE OF provider ON dns_records
        FOR EACH ROW
        WHEN NEW.provider != OLD.provider
        BEGIN
            INSERT OR IGNORE INTO provider_accounts (provider, name, enabled)
            VALUES (NEW.provider, 'Default', 1);

            UPDATE dns_records
            SET provider_account_id = (
                SELECT id
                FROM provider_accounts
                WHERE provider = NEW.provider
                  AND name = 'Default'
                ORDER BY id
                LIMIT 1
            )
            WHERE id = NEW.id;
        END
        """
    )


def _dns_records_schema_sql(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("dns_records",),
    ).fetchone()
    return row["sql"] or "" if row else ""


def _ensure_dns_records_unique_by_account(conn: sqlite3.Connection) -> None:
    schema_sql = _dns_records_schema_sql(conn)
    if "UNIQUE(provider, domain)" not in schema_sql:
        return

    conn.execute("DROP TRIGGER IF EXISTS dns_records_assign_provider_account_id_insert")
    conn.execute("DROP TRIGGER IF EXISTS dns_records_assign_provider_account_id_update")
    conn.execute("ALTER TABLE dns_records RENAME TO dns_records_old")
    conn.execute(
        """
        CREATE TABLE dns_records (
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
            provider_account_id INTEGER,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(provider_account_id, domain)
        )
        """
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO dns_records (
            id,
            provider,
            domain,
            zone_id,
            zone_name,
            record_name,
            record_type,
            proxied,
            ttl,
            provider_record_id,
            provider_account_id,
            enabled,
            created_at
        )
        SELECT
            id,
            provider,
            domain,
            zone_id,
            zone_name,
            record_name,
            record_type,
            proxied,
            ttl,
            provider_record_id,
            provider_account_id,
            enabled,
            created_at
        FROM dns_records_old
        """
    )
    conn.execute("DROP TABLE dns_records_old")


def _migrate_provider_accounts(conn: sqlite3.Connection) -> None:
    from .provider_accounts import (
        DEFAULT_PROVIDER_ACCOUNT_NAME,
        ensure_provider_account,
        sync_dns_records_provider_account_ids,
    )

    for provider in sorted(_configured_providers(conn)):
        ensure_provider_account(
            provider,
            DEFAULT_PROVIDER_ACCOUNT_NAME,
            secret=_config_secret(conn, provider),
            conn=conn,
        )

    sync_dns_records_provider_account_ids(
        conn=conn,
        provider_account_name=DEFAULT_PROVIDER_ACCOUNT_NAME,
        create_missing=True,
    )


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
        from .provider_accounts import ensure_provider_accounts_table

        ensure_provider_accounts_table(conn=conn)
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
                provider_account_id INTEGER,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider_account_id, domain)
            )
            """
        )

        _ensure_dns_records_provider_account_id(conn)
        import_legacy_sqlite(conn)
        _migrate_provider_accounts(conn)
        _ensure_dns_records_unique_by_account(conn)
        _ensure_dns_records_provider_account_triggers(conn)
