import aiohttp

HOSTING_1984_ENDPOINT = "https://api.1984.is/1.0/freedns/"


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
        async with session.get(HOSTING_1984_ENDPOINT, params=params, timeout=15) as response:
            body = (await response.text()).strip()
            if response.status == 200:
                return {"success": True, "message": "DNS запись обновлена"}
            return {"success": False, "message": f"HTTP {response.status}: {body or 'ошибка API'}"}
    except Exception as exc:
        return {"success": False, "message": f"сетевая ошибка: {exc}"}

