import logging
import sqlite3
from typing import Any

from .constants import provider_label
from .core import _connect

logger = logging.getLogger(__name__)


def add_record(
    provider: str,
    domain: str,
    *,
    zone_id: str | None = None,
    zone_name: str | None = None,
    record_name: str | None = None,
    record_type: str = "A",
    proxied: bool = False,
    ttl: int = 1,
    provider_record_id: str | None = None,
) -> bool:
    try:
        with _connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO dns_records (
                    provider,
                    domain,
                    zone_id,
                    zone_name,
                    record_name,
                    record_type,
                    proxied,
                    ttl,
                    provider_record_id,
                    enabled
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    provider,
                    domain,
                    zone_id,
                    zone_name,
                    record_name,
                    record_type,
                    int(proxied),
                    ttl,
                    provider_record_id,
                ),
            )
        logger.info("Создана запись #%s: %s | %s", cursor.lastrowid, provider_label(provider), domain)
        return True
    except sqlite3.IntegrityError:
        return False


def list_records(provider: str | None = None) -> list[dict[str, Any]]:
    query = """
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
            enabled,
            created_at
        FROM dns_records
    """
    params: tuple[Any, ...] = ()
    if provider:
        query += " WHERE provider = ?"
        params = (provider,)
    query += " ORDER BY provider, domain"

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]


def get_record(record_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
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
                enabled,
                created_at
            FROM dns_records
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
    return dict(row) if row else None


def update_record(
    record_id: int,
    *,
    zone_id: str | None = None,
    zone_name: str | None = None,
    record_name: str | None = None,
    proxied: bool | None = None,
    ttl: int | None = None,
    provider_record_id: str | None = None,
) -> None:
    record = get_record(record_id)
    assignments: list[str] = []
    params: list[Any] = []

    if zone_id is not None:
        assignments.append("zone_id = ?")
        params.append(zone_id)
    if zone_name is not None:
        assignments.append("zone_name = ?")
        params.append(zone_name)
    if record_name is not None:
        assignments.append("record_name = ?")
        params.append(record_name)
    if proxied is not None:
        assignments.append("proxied = ?")
        params.append(int(proxied))
    if ttl is not None:
        assignments.append("ttl = ?")
        params.append(ttl)
    if provider_record_id is not None:
        assignments.append("provider_record_id = ?")
        params.append(provider_record_id)

    if not assignments:
        return

    params.append(record_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE dns_records SET {', '.join(assignments)} WHERE id = ?",
            tuple(params),
        )

    if record:
        changes: list[str] = []
        if zone_name is not None and zone_name != record["zone_name"]:
            changes.append(f"зона={zone_name}")
        elif zone_id is not None and zone_id != record["zone_id"]:
            changes.append(f"zone_id={zone_id}")
        if record_name is not None and record_name != record["record_name"]:
            changes.append(f"имя={record_name}")
        if proxied is not None and int(proxied) != record["proxied"]:
            changes.append(f"proxy={'включен' if proxied else 'выключен'}")
        if ttl is not None and ttl != record["ttl"]:
            changes.append(f"ttl={ttl}")
        if provider_record_id is not None and provider_record_id != record["provider_record_id"]:
            changes.append("provider_record_id обновлен")

        if changes:
            logger.info(
                "Обновлена запись #%s: %s | %s (%s)",
                record_id,
                provider_label(record["provider"]),
                record["domain"],
                ", ".join(changes),
            )


def delete_record(record_id: int) -> None:
    record = get_record(record_id)
    with _connect() as conn:
        conn.execute("DELETE FROM dns_records WHERE id = ?", (record_id,))

    if record:
        logger.info(
            "Удалена запись #%s: %s | %s",
            record_id,
            provider_label(record["provider"]),
            record["domain"],
        )
