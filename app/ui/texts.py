from collections import Counter

from app import db
from app.config import CHECK_INTERVAL
from app.services.domains import provider_label


def build_main_text() -> str:
    return (
        "MK_DDNS\n\n"
        "Один Telegram-бот для управления DDNS на 1984Hosting и Cloudflare.\n"
        "Основная работа вынесена в кнопки и меню.\n\n"
        "Что можно делать:\n"
        "• задавать ключи провайдеров\n"
        "• добавлять и удалять записи\n"
        "• вручную запускать обновление\n"
        "• смотреть статус IP и настроек"
    )


def build_provider_text() -> str:
    key_1984 = "установлен" if db.get_provider_secret(db.PROVIDER_1984) else "не задан"
    key_cf = "установлен" if db.get_provider_secret(db.PROVIDER_CLOUDFLARE) else "не задан"
    return (
        "Провайдеры\n\n"
        f"• 1984Hosting API key: {key_1984}\n"
        f"• Cloudflare API token: {key_cf}\n\n"
        "Для Cloudflare используйте токен c правами Zone:Read и DNS:Edit."
    )


def build_records_text(records: list[dict]) -> str:
    if not records:
        return (
            "Записи пока не добавлены.\n\n"
            "Добавьте запись через кнопки ниже. Для Cloudflare сначала задайте API token."
        )

    lines = ["Текущие записи:", ""]
    for record in records:
        extra = ""
        if record["provider"] == db.PROVIDER_CLOUDFLARE:
            proxy_status = "proxy" if record["proxied"] else "dns only"
            extra = f" | зона: {record['zone_name']} | {proxy_status}"
        lines.append(
            f"#{record['id']} | {provider_label(record['provider'])} | {record['domain']}{extra}"
        )
    return "\n".join(lines)


def build_status_text() -> str:
    records = db.list_records()
    counter = Counter(record["provider"] for record in records)
    last_ip = db.get_last_global_ip() or "еще не определен"

    return (
        "Статус MK_DDNS\n\n"
        f"• Последний внешний IP: {last_ip}\n"
        f"• 1984Hosting key: {'✅' if db.get_provider_secret(db.PROVIDER_1984) else '❌'}\n"
        f"• Cloudflare token: {'✅' if db.get_provider_secret(db.PROVIDER_CLOUDFLARE) else '❌'}\n"
        f"• Записей 1984Hosting: {counter.get(db.PROVIDER_1984, 0)}\n"
        f"• Записей Cloudflare: {counter.get(db.PROVIDER_CLOUDFLARE, 0)}\n"
        f"• Интервал проверки: {CHECK_INTERVAL} сек."
    )
