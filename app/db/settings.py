import logging

from .constants import PROVIDER_1984, _secret_key, provider_label
from .core import _connect
from .provider_accounts import get_provider_account_secret, set_provider_account_secret

logger = logging.getLogger(__name__)


def get_config(key: str) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT value FROM config WHERE key = ?",
            (key,),
        ).fetchone()
    return row["value"] if row else None


def set_config(key: str, value: str | None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, value),
        )


def _config_provider_secret(conn, provider: str) -> str | None:
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


def _set_config_provider_secret(conn, provider: str, secret: str | None) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
        (_secret_key(provider), secret),
    )
    if provider == PROVIDER_1984:
        conn.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            ("api_key", secret),
        )


def set_provider_secret(provider: str, secret: str | None) -> None:
    with _connect() as conn:
        set_provider_account_secret(provider, secret, conn=conn)
        _set_config_provider_secret(conn, provider, secret)
    logger.info("Сохранены настройки провайдера %s", provider_label(provider))


def get_provider_secret(provider: str) -> str | None:
    with _connect() as conn:
        account_secret = get_provider_account_secret(provider, conn=conn)
        if account_secret is not None:
            return account_secret

        return _config_provider_secret(conn, provider)


def get_last_global_ip() -> str | None:
    return get_config("last_global_ip")


def set_last_global_ip(ip: str) -> None:
    set_config("last_global_ip", ip)
