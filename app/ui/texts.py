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
        "• добавлять аккаунты провайдеров\n"
        "• добавлять и удалять записи\n"
        "• вручную запускать обновление\n"
        "• смотреть статус IP, аккаунтов и записей"
    )


def build_provider_text() -> str:
    accounts = db.list_provider_accounts()
    if not accounts:
        return (
            "Провайдеры\n\n"
            "Аккаунты провайдеров пока не добавлены.\n\n"
            "Добавьте отдельный аккаунт для каждого 1984Hosting API key или Cloudflare token."
        )

    lines = ["Провайдеры", ""]
    for account in accounts:
        status = "включен" if account["enabled"] else "выключен"
        secret_status = "ключ задан" if account["secret"] else "ключ не задан"
        lines.append(
            f"• #{account['id']} | {provider_label(account['provider'])} | {account['name']} | {status}, {secret_status}"
        )
    lines.extend(
        [
            "",
            "Для Cloudflare используйте токен c правами Zone:Read и DNS:Edit.",
        ]
    )
    return "\n".join(lines)


def build_records_text(records: list[dict]) -> str:
    if not records:
        return (
            "Записи пока не добавлены.\n\n"
            "Добавьте запись через кнопки ниже. Для Cloudflare сначала добавьте аккаунт с API token."
        )

    lines = ["Текущие записи:", ""]
    for record in records:
        account_name = record.get("provider_account_name") or "аккаунт не выбран"
        extra = ""
        if record["provider"] == db.PROVIDER_CLOUDFLARE:
            proxy_status = "proxy" if record["proxied"] else "dns only"
            extra = f" | зона: {record['zone_name']} | {proxy_status}"
        lines.append(
            f"#{record['id']} | {provider_label(record['provider'])} / {account_name} | {record['domain']}{extra}"
        )
    return "\n".join(lines)


def build_status_text() -> str:
    records = db.list_records()
    accounts = db.list_provider_accounts()
    counter = Counter(record["provider"] for record in records)
    account_counter = Counter(account["provider"] for account in accounts)
    last_ip = db.get_last_global_ip() or "еще не определен"

    return (
        "Статус MK_DDNS\n\n"
        f"• Последний внешний IP: {last_ip}\n"
        f"• Аккаунтов 1984Hosting: {account_counter.get(db.PROVIDER_1984, 0)}\n"
        f"• Аккаунтов Cloudflare: {account_counter.get(db.PROVIDER_CLOUDFLARE, 0)}\n"
        f"• Записей 1984Hosting: {counter.get(db.PROVIDER_1984, 0)}\n"
        f"• Записей Cloudflare: {counter.get(db.PROVIDER_CLOUDFLARE, 0)}\n"
        f"• Интервал проверки: {CHECK_INTERVAL} сек."
    )
