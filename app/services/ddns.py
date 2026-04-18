import asyncio
import logging

from aiogram import Bot
import aiohttp

from app import db, providers
from app.config import ADMIN_ID, CHECK_INTERVAL
from app.services.domains import provider_label
from app.ui.keyboards import main_reply_keyboard

logger = logging.getLogger(__name__)


def _record_log_prefix(record: dict) -> str:
    return f"#{record['id']} | {provider_label(record['provider'])} | {record['domain']}"


async def perform_ddns_update(force: bool = False) -> str | None:
    records = db.list_records()
    if not records:
        if force:
            logger.info("DDNS-проверка пропущена: в базе нет ни одной DNS-записи.")
        return "Записей нет. Добавьте хотя бы одну запись через меню." if force else None

    try:
        async with aiohttp.ClientSession() as session:
            current_ip = await providers.get_public_ip(session)
            last_ip = db.get_last_global_ip()

            if not force and current_ip == last_ip:
                logger.info(
                    "Внешний IP не изменился: %s. Обновление %s записей не требуется.",
                    current_ip,
                    len(records),
                )
                return None

            if force:
                logger.info(
                    "Запущено принудительное DDNS-обновление: IP=%s, записей=%s.",
                    current_ip,
                    len(records),
                )
            elif last_ip:
                logger.info("Обнаружена смена внешнего IP: %s -> %s.", last_ip, current_ip)
            else:
                logger.info("Зафиксирован текущий внешний IP: %s.", current_ip)

            results = []
            success_count = 0
            failed_count = 0
            skipped_count = 0
            for record in records:
                record_prefix = _record_log_prefix(record)
                provider = record["provider"]
                if provider == db.PROVIDER_1984:
                    api_key = db.get_provider_secret(db.PROVIDER_1984)
                    if not api_key:
                        skipped_count += 1
                        logger.warning("%s: запись пропущена, не задан API key 1984Hosting.", record_prefix)
                        results.append(f"🌐 {record['domain']}: пропущено, не задан API key 1984Hosting")
                        continue

                    result = await providers.update_1984_record(
                        session,
                        api_key=api_key,
                        domain=record["domain"],
                        current_ip=current_ip,
                    )
                    if result["success"]:
                        success_count += 1
                        logger.info(
                            "%s: %s. Новый IP=%s.",
                            record_prefix,
                            result["message"],
                            current_ip,
                        )
                    else:
                        failed_count += 1
                        logger.warning(
                            "%s: ошибка обновления: %s.",
                            record_prefix,
                            result["message"],
                        )
                    status = "✅" if result["success"] else "❌"
                    results.append(f"🌐 {record['domain']}: {status} {result['message']}")
                    continue

                if provider == db.PROVIDER_CLOUDFLARE:
                    token = db.get_provider_secret(db.PROVIDER_CLOUDFLARE)
                    if not token:
                        skipped_count += 1
                        logger.warning("%s: запись пропущена, не задан Cloudflare token.", record_prefix)
                        results.append(f"☁️ {record['domain']}: пропущено, не задан Cloudflare token")
                        continue

                    if not record["zone_id"] or not record["zone_name"]:
                        skipped_count += 1
                        logger.warning(
                            "%s: запись пропущена, не указаны zone_id/zone_name Cloudflare.",
                            record_prefix,
                        )
                        results.append(f"☁️ {record['domain']}: пропущено, не задана зона Cloudflare")
                        continue

                    result = await providers.ensure_cloudflare_a_record(
                        session,
                        token=token,
                        zone_id=record["zone_id"],
                        fqdn=record["domain"],
                        current_ip=current_ip,
                        proxied=bool(record["proxied"]),
                        ttl=int(record["ttl"] or 1),
                        record_id=record["provider_record_id"],
                    )
                    if result.get("record_id") and result["record_id"] != record["provider_record_id"]:
                        db.update_record(record["id"], provider_record_id=result["record_id"])
                        logger.info("%s: сохранен Cloudflare record_id=%s.", record_prefix, result["record_id"])

                    if result["success"]:
                        success_count += 1
                        logger.info(
                            "%s: %s. Новый IP=%s, proxied=%s, ttl=%s.",
                            record_prefix,
                            result["message"],
                            current_ip,
                            bool(record["proxied"]),
                            int(record["ttl"] or 1),
                        )
                    else:
                        failed_count += 1
                        logger.warning(
                            "%s: ошибка обновления: %s.",
                            record_prefix,
                            result["message"],
                        )
                    status = "✅" if result["success"] else "❌"
                    results.append(f"☁️ {record['domain']}: {status} {result['message']}")
                    continue

                failed_count += 1
                logger.warning("%s: запись не обработана, неизвестный провайдер %s.", record_prefix, provider)
                results.append(f"{record['domain']}: ❌ неизвестный провайдер {provider}")

            db.set_last_global_ip(current_ip)
            logger.info(
                "DDNS-обновление завершено: IP=%s, успешно=%s, ошибок=%s, пропущено=%s.",
                current_ip,
                success_count,
                failed_count,
                skipped_count,
            )
            mode = "Принудительное обновление" if force else "IP изменился"
            return f"{mode}\nТекущий IP: {current_ip}\n\n" + "\n".join(results)
    except Exception as exc:
        logger.exception("Ошибка DDNS-обновления")
        return f"Ошибка DDNS-обновления: {exc}"


async def ddns_loop(bot: Bot) -> None:
    while True:
        report = await perform_ddns_update(force=False)
        if report:
            await bot.send_message(
                ADMIN_ID,
                report,
                reply_markup=main_reply_keyboard(),
            )
        await asyncio.sleep(CHECK_INTERVAL)
