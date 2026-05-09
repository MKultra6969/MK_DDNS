import asyncio
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp

HOSTING_1984_ENDPOINT = "https://api.1984.is/1.0/freedns/"


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


HOSTING_1984_REQUEST_INTERVAL_SECONDS = max(
    0.0,
    _env_float("HOSTING_1984_REQUEST_INTERVAL_SECONDS", 5.0),
)
HOSTING_1984_MAX_ATTEMPTS = max(1, _env_int("HOSTING_1984_MAX_ATTEMPTS", 3))
HOSTING_1984_BACKOFF_SECONDS = max(0.0, _env_float("HOSTING_1984_BACKOFF_SECONDS", 5.0))

_hosting_1984_lock: asyncio.Lock | None = None
_hosting_1984_next_request_at = 0.0


def _get_hosting_1984_lock() -> asyncio.Lock:
    global _hosting_1984_lock
    if _hosting_1984_lock is None:
        _hosting_1984_lock = asyncio.Lock()
    return _hosting_1984_lock


async def _wait_for_hosting_1984_slot() -> None:
    global _hosting_1984_next_request_at
    async with _get_hosting_1984_lock():
        now = time.monotonic()
        wait_seconds = max(0.0, _hosting_1984_next_request_at - now)
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
            now = time.monotonic()
        _hosting_1984_next_request_at = now + HOSTING_1984_REQUEST_INTERVAL_SECONDS


def _retry_after_seconds(retry_after: str | None) -> float | None:
    if not retry_after:
        return None

    retry_after = retry_after.strip()
    if not retry_after:
        return None

    try:
        return max(0.0, float(retry_after))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(retry_after)
    except (TypeError, ValueError, OverflowError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)

    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def _rate_limit_message(retry_after: float | None) -> str:
    message = (
        "Сервис 1984Hosting временно ограничил запросы (429). "
        "Я подождал и повторил запрос, но лимит все еще действует."
    )
    if retry_after and retry_after > 0:
        message += f" Провайдер просит подождать еще примерно {retry_after:.0f} сек."
    return f"{message} Попробуйте обновить запись позже."


async def update_1984_record(
    session: aiohttp.ClientSession,
    *,
    api_key: str,
    domain: str,
    current_ip: str,
) -> dict:
    params = {
        "apikey": api_key,
        "domain": domain,
        "ip": current_ip,
    }

    try:
        for attempt in range(1, HOSTING_1984_MAX_ATTEMPTS + 1):
            await _wait_for_hosting_1984_slot()
            async with session.get(HOSTING_1984_ENDPOINT, params=params, timeout=15) as response:
                body = (await response.text()).strip()
                if response.status == 200:
                    return {"success": True, "message": "DNS запись обновлена"}

                if response.status == 429:
                    retry_after = _retry_after_seconds(response.headers.get("Retry-After"))
                    if attempt < HOSTING_1984_MAX_ATTEMPTS:
                        wait_seconds = (
                            retry_after
                            if retry_after and retry_after > 0
                            else HOSTING_1984_BACKOFF_SECONDS * (2 ** (attempt - 1))
                        )
                        await asyncio.sleep(wait_seconds)
                        continue

                    return {
                        "success": False,
                        "message": _rate_limit_message(retry_after),
                    }

                return {"success": False, "message": f"HTTP {response.status}: {body or 'ошибка API'}"}
    except Exception as exc:
        return {"success": False, "message": f"сетевая ошибка: {exc}"}
