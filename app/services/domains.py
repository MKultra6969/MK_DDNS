from app import db


def provider_label(provider: str) -> str:
    return db.PROVIDER_LABELS.get(provider, provider)


def normalize_cloudflare_name(zone_name: str, raw_value: str) -> tuple[str, str]:
    zone = zone_name.strip().lower().rstrip(".")
    value = raw_value.strip().lower().rstrip(".")

    if not value:
        raise ValueError("Имя записи не должно быть пустым.")

    if value == "@":
        return zone, "@"

    if value == zone:
        return zone, "@"

    if value.endswith(f".{zone}"):
        relative = value[: -(len(zone) + 1)]
        if not relative:
            return zone, "@"
        return value, relative

    if "." in value:
        raise ValueError(f"Запись должна принадлежать зоне {zone}.")

    return f"{value}.{zone}", value
