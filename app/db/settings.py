import logging

from .constants import _secret_key, provider_label
from .core import _connect

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


def set_provider_secret(provider: str, secret: str) -> None:
    set_config(_secret_key(provider), secret)
    logger.info("Сохранены настройки провайдера %s", provider_label(provider))


def get_provider_secret(provider: str) -> str | None:
    return get_config(_secret_key(provider))


def get_last_global_ip() -> str | None:
    return get_config("last_global_ip")


def set_last_global_ip(ip: str) -> None:
    set_config("last_global_ip", ip)
