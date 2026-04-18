import logging

import aiohttp

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from app import db, providers
from app.services.domains import normalize_cloudflare_name, provider_label
from app.states import DDNSFSM
from app.ui import (
    back_to_providers_keyboard,
    back_to_records_keyboard,
    build_records_text,
    delete_confirm_keyboard,
    main_reply_keyboard,
    proxied_inline_keyboard,
    records_inline_keyboard,
    records_list_keyboard,
    safe_edit_menu,
    zone_inline_keyboard,
)

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "records:add:1984")
async def records_add_1984(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(DDNSFSM.add_1984_domain)
    await call.answer()
    await call.message.answer(
        "Введите полный домен для 1984Hosting.\nПример: home.example.com",
        reply_markup=back_to_records_keyboard(),
    )


@router.message(DDNSFSM.add_1984_domain)
async def process_add_1984_domain(message: types.Message, state: FSMContext) -> None:
    domain = (message.text or "").strip().lower().rstrip(".")
    if not domain or "." not in domain:
        await message.answer("Нужен полный домен, например home.example.com")
        return

    created = db.add_record(db.PROVIDER_1984, domain)
    if created:
        logger.info(
            "Добавлена DNS-запись: %s | %s | admin_id=%s.",
            provider_label(db.PROVIDER_1984),
            domain,
            message.from_user.id if message.from_user else "unknown",
        )
    else:
        logger.info(
            "Повторная попытка добавить существующую DNS-запись: %s | %s | admin_id=%s.",
            provider_label(db.PROVIDER_1984),
            domain,
            message.from_user.id if message.from_user else "unknown",
        )
    await state.clear()
    text = (
        f"Запись {domain} уже существует."
        if not created
        else f"Запись {domain} добавлена для 1984Hosting."
    )
    await message.answer(text, reply_markup=main_reply_keyboard())
    await message.answer(build_records_text(db.list_records()), reply_markup=records_inline_keyboard())


@router.callback_query(F.data == "records:add:cloudflare")
async def records_add_cloudflare(call: types.CallbackQuery, state: FSMContext) -> None:
    token = db.get_provider_secret(db.PROVIDER_CLOUDFLARE)
    if not token:
        await call.answer("Сначала задайте Cloudflare token.", show_alert=True)
        return

    async with aiohttp.ClientSession() as session:
        zones_result = await providers.list_cloudflare_zones(session, token)

    if not zones_result["success"]:
        await call.answer("Не удалось получить зоны Cloudflare.", show_alert=True)
        await call.message.answer(
            f"Ошибка Cloudflare: {zones_result['message']}",
            reply_markup=back_to_providers_keyboard(),
        )
        return

    zones = zones_result["zones"]
    if not zones:
        await call.answer("У токена нет доступных зон.", show_alert=True)
        return

    await state.clear()
    await state.update_data(cf_zones=zones)
    await call.answer()
    await call.message.answer(
        "Выберите Cloudflare-зону для новой записи.",
        reply_markup=zone_inline_keyboard(zones),
    )


@router.callback_query(F.data.startswith("cfzone:"))
async def cloudflare_zone_selected(call: types.CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    zones = data.get("cf_zones") or []
    try:
        zone_index = int(call.data.split(":")[1])
        zone = zones[zone_index]
    except (IndexError, ValueError):
        await call.answer("Список зон устарел. Откройте меню добавления снова.", show_alert=True)
        return

    await state.update_data(selected_zone=zone)
    await state.set_state(DDNSFSM.add_cloudflare_name)
    await call.answer()
    await call.message.answer(
        f"Зона выбрана: {zone['name']}\nТеперь отправьте имя записи внутри этой зоны.\nПримеры: @, home, vpn",
        reply_markup=back_to_records_keyboard(),
    )


@router.message(DDNSFSM.add_cloudflare_name)
async def process_cloudflare_name(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    zone = data.get("selected_zone")
    if not zone:
        await state.clear()
        await message.answer("Выбор зоны потерян. Начните добавление заново.")
        return

    try:
        fqdn, record_name = normalize_cloudflare_name(zone["name"], message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return

    await state.update_data(
        pending_cloudflare_domain=fqdn,
        pending_cloudflare_record_name=record_name,
    )
    await state.set_state(DDNSFSM.add_cloudflare_proxied)
    await message.answer(
        f"Запись будет создана как {fqdn}\nВыберите режим Cloudflare:",
        reply_markup=proxied_inline_keyboard(),
    )


@router.callback_query(DDNSFSM.add_cloudflare_proxied, F.data.startswith("cfproxy:"))
async def process_cloudflare_proxied(call: types.CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    zone = data.get("selected_zone")
    fqdn = data.get("pending_cloudflare_domain")
    record_name = data.get("pending_cloudflare_record_name")
    proxied = call.data.endswith(":1")

    if not zone or not fqdn or record_name is None:
        await state.clear()
        await call.answer("Состояние добавления потеряно. Начните заново.", show_alert=True)
        return

    created = db.add_record(
        db.PROVIDER_CLOUDFLARE,
        fqdn,
        zone_id=zone["id"],
        zone_name=zone["name"],
        record_name=record_name,
        proxied=proxied,
        ttl=1,
    )
    if created:
        logger.info(
            "Добавлена DNS-запись: %s | %s | zone=%s | proxied=%s | admin_id=%s.",
            provider_label(db.PROVIDER_CLOUDFLARE),
            fqdn,
            zone["name"],
            proxied,
            call.from_user.id,
        )
    else:
        logger.info(
            "Повторная попытка добавить существующую DNS-запись: %s | %s | zone=%s | admin_id=%s.",
            provider_label(db.PROVIDER_CLOUDFLARE),
            fqdn,
            zone["name"],
            call.from_user.id,
        )
    await state.clear()
    await call.answer()

    text = f"Cloudflare-запись {fqdn} добавлена." if created else f"Запись {fqdn} уже существует."
    await call.message.answer(text, reply_markup=main_reply_keyboard())
    await call.message.answer(build_records_text(db.list_records()), reply_markup=records_inline_keyboard())


@router.callback_query(F.data == "records:list")
async def records_list(call: types.CallbackQuery) -> None:
    records = db.list_records()
    markup = records_list_keyboard(records) if records else back_to_records_keyboard()
    await safe_edit_menu(call, build_records_text(records), markup)


@router.callback_query(F.data.startswith("record:delete:"))
async def record_delete_prompt(call: types.CallbackQuery) -> None:
    try:
        record_id = int(call.data.rsplit(":", 1)[1])
    except ValueError:
        await call.answer()
        return

    record = db.get_record(record_id)
    if not record:
        await call.answer("Запись уже удалена.", show_alert=True)
        return

    await safe_edit_menu(
        call,
        f"Удалить запись?\n\n#{record['id']} | {provider_label(record['provider'])} | {record['domain']}",
        delete_confirm_keyboard(record_id),
    )


@router.callback_query(F.data.startswith("record:confirm_delete:"))
async def record_confirm_delete(call: types.CallbackQuery) -> None:
    try:
        record_id = int(call.data.rsplit(":", 1)[1])
    except ValueError:
        await call.answer()
        return

    record = db.get_record(record_id)
    if not record:
        logger.info("Попытка удалить отсутствующую DNS-запись: #%s | admin_id=%s.", record_id, call.from_user.id)
        await call.answer("Запись уже удалена.", show_alert=True)
        return

    db.delete_record(record_id)
    logger.info(
        "Удалена DNS-запись: #%s | %s | %s | admin_id=%s.",
        record["id"],
        provider_label(record["provider"]),
        record["domain"],
        call.from_user.id,
    )
    records = db.list_records()
    markup = records_list_keyboard(records) if records else back_to_records_keyboard()
    await safe_edit_menu(call, build_records_text(records), markup)
