import aiohttp

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4"


def _cloudflare_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _cloudflare_error(payload: dict | None, fallback: str) -> str:
    if not payload:
        return fallback

    errors = payload.get("errors") or []
    if errors:
        first = errors[0]
        code = first.get("code")
        message = first.get("message") or fallback
        return f"{code}: {message}" if code else message

    messages = payload.get("messages") or []
    if messages:
        first = messages[0]
        message = first.get("message")
        if message:
            return message

    return fallback


async def _cloudflare_json(
    session: aiohttp.ClientSession,
    method: str,
    path: str,
    token: str,
    **kwargs,
) -> tuple[int, dict | None]:
    async with session.request(
        method,
        f"{CLOUDFLARE_API_BASE}{path}",
        headers=_cloudflare_headers(token),
        timeout=20,
        **kwargs,
    ) as response:
        try:
            payload = await response.json()
        except Exception:
            payload = None
        return response.status, payload


async def validate_cloudflare_token(session: aiohttp.ClientSession, token: str) -> dict:
    status, payload = await _cloudflare_json(session, "GET", "/zones?per_page=1", token)
    if status == 200 and payload and payload.get("success"):
        return {"success": True, "message": "токен валиден"}
    return {
        "success": False,
        "message": _cloudflare_error(payload, f"HTTP {status}: токен не принят"),
    }


async def list_cloudflare_zones(session: aiohttp.ClientSession, token: str) -> dict:
    status, payload = await _cloudflare_json(session, "GET", "/zones?per_page=50", token)
    if status == 200 and payload and payload.get("success"):
        zones = [
            {"id": zone["id"], "name": zone["name"]}
            for zone in payload.get("result", [])
            if zone.get("id") and zone.get("name")
        ]
        zones.sort(key=lambda item: item["name"])
        return {"success": True, "message": "ok", "zones": zones}

    return {
        "success": False,
        "message": _cloudflare_error(payload, f"HTTP {status}: не удалось получить зоны"),
        "zones": [],
    }


async def _find_cloudflare_record_id(
    session: aiohttp.ClientSession,
    token: str,
    zone_id: str,
    fqdn: str,
) -> dict:
    status, payload = await _cloudflare_json(
        session,
        "GET",
        f"/zones/{zone_id}/dns_records",
        token,
        params={"type": "A", "name": fqdn},
    )
    if status == 200 and payload and payload.get("success"):
        results = payload.get("result", [])
        if results:
            return {
                "success": True,
                "message": "ok",
                "record_id": results[0]["id"],
            }
        return {"success": True, "message": "запись не найдена", "record_id": None}

    return {
        "success": False,
        "message": _cloudflare_error(payload, f"HTTP {status}: не удалось получить DNS записи"),
        "record_id": None,
    }


async def ensure_cloudflare_a_record(
    session: aiohttp.ClientSession,
    *,
    token: str,
    zone_id: str,
    fqdn: str,
    current_ip: str,
    proxied: bool = False,
    ttl: int = 1,
    record_id: str | None = None,
) -> dict:
    body = {
        "type": "A",
        "name": fqdn,
        "content": current_ip,
        "proxied": proxied,
        "ttl": ttl,
    }

    target_record_id = record_id
    if not target_record_id:
        lookup = await _find_cloudflare_record_id(session, token, zone_id, fqdn)
        if not lookup["success"]:
            return lookup
        target_record_id = lookup["record_id"]

    if target_record_id:
        status, payload = await _cloudflare_json(
            session,
            "PATCH",
            f"/zones/{zone_id}/dns_records/{target_record_id}",
            token,
            json=body,
        )
        if status == 200 and payload and payload.get("success"):
            return {
                "success": True,
                "message": "DNS запись обновлена",
                "record_id": target_record_id,
            }

        lookup = await _find_cloudflare_record_id(session, token, zone_id, fqdn)
        if not lookup["success"]:
            return lookup
        target_record_id = lookup["record_id"]
        if target_record_id:
            status, payload = await _cloudflare_json(
                session,
                "PATCH",
                f"/zones/{zone_id}/dns_records/{target_record_id}",
                token,
                json=body,
            )
            if status == 200 and payload and payload.get("success"):
                return {
                    "success": True,
                    "message": "DNS запись обновлена",
                    "record_id": target_record_id,
                }

    status, payload = await _cloudflare_json(
        session,
        "POST",
        f"/zones/{zone_id}/dns_records",
        token,
        json=body,
    )
    if status in (200, 201) and payload and payload.get("success"):
        created_id = (payload.get("result") or {}).get("id")
        return {
            "success": True,
            "message": "DNS запись создана",
            "record_id": created_id,
        }

    return {
        "success": False,
        "message": _cloudflare_error(payload, f"HTTP {status}: не удалось записать DNS запись"),
        "record_id": target_record_id,
    }

