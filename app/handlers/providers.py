import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
import aiohttp

from app import db, providers
from app.services.domains import provider_label
from app.states import DDNSFSM
from app.ui import back_to_providers_keyboard, build_provider_text, main_reply_keyboard, providers_inline_keyboard

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "provider:set:1984")
async def provider_set_1984(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(provider_account_name=db.DEFAULT_PROVIDER_ACCOUNT_NAME)
    await state.set_state(DDNSFSM.set_1984_key)
    await call.answer()
    await call.message.answer(
        f"Отправьте API key от 1984Hosting для аккаунта {db.DEFAULT_PROVIDER_ACCOUNT_NAME}.",
        reply_markup=back_to_providers_keyboard(),
    )


@router.callback_query(F.data == "provider:set:cloudflare")
async def provider_set_cloudflare(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(provider_account_name=db.DEFAULT_PROVIDER_ACCOUNT_NAME)
    await state.set_state(DDNSFSM.set_cloudflare_token)
    await call.answer()
    await call.message.answer(
        f"Отправьте Cloudflare API token для аккаунта {db.DEFAULT_PROVIDER_ACCOUNT_NAME}.\n"
        "Нужны права Zone:Read и DNS:Edit.",
        reply_markup=back_to_providers_keyboard(),
    )


@router.callback_query(F.data.startswith("provider:add:"))
async def provider_add_account(call: types.CallbackQuery, state: FSMContext) -> None:
    provider_key = call.data.rsplit(":", 1)[1]
    provider = db.PROVIDER_1984 if provider_key == "1984" else db.PROVIDER_CLOUDFLARE
    await state.clear()
    await state.update_data(pending_provider=provider)
    await state.set_state(DDNSFSM.add_provider_account_name)
    await call.answer()
    await call.message.answer(
        f"Введите имя аккаунта {provider_label(provider)}.\nПример: Мой аккаунт или Клиент Иван",
        reply_markup=back_to_providers_keyboard(),
    )


@router.message(DDNSFSM.add_provider_account_name)
async def process_provider_account_name(message: types.Message, state: FSMContext) -> None:
    data = await state.get_data()
    provider = data.get("pending_provider")
    if provider not in (db.PROVIDER_1984, db.PROVIDER_CLOUDFLARE):
        await state.clear()
        await message.answer("Провайдер не выбран. Начните добавление аккаунта заново.")
        return

    account_name = (message.text or "").strip()
    if not account_name:
        await message.answer("Имя аккаунта не должно быть пустым.")
        return
    if len(account_name) > 60:
        await message.answer("Имя аккаунта слишком длинное. Используйте до 60 символов.")
        return

    await state.update_data(provider_account_name=account_name)
    if provider == db.PROVIDER_1984:
        await state.set_state(DDNSFSM.set_1984_key)
        await message.answer(
            f"Отправьте API key от 1984Hosting для аккаунта {account_name}.",
            reply_markup=back_to_providers_keyboard(),
        )
        return

    await state.set_state(DDNSFSM.set_cloudflare_token)
    await message.answer(
        f"Отправьте Cloudflare API token для аккаунта {account_name}.\n"
        "Нужны права Zone:Read и DNS:Edit.",
        reply_markup=back_to_providers_keyboard(),
    )


@router.message(DDNSFSM.set_1984_key)
async def process_1984_key(message: types.Message, state: FSMContext) -> None:
    secret = (message.text or "").strip()
    if not secret:
        await message.answer("API key пустой. Попробуйте еще раз.")
        return

    data = await state.get_data()
    account_name = data.get("provider_account_name") or db.DEFAULT_PROVIDER_ACCOUNT_NAME
    db.set_provider_account_secret(db.PROVIDER_1984, secret, account_name)
    logger.info(
        "Сохранен аккаунт провайдера: %s | %s | admin_id=%s.",
        provider_label(db.PROVIDER_1984),
        account_name,
        message.from_user.id if message.from_user else "unknown",
    )
    await state.clear()
    await message.answer(f"Аккаунт 1984Hosting {account_name} сохранен.", reply_markup=main_reply_keyboard())
    await message.answer(build_provider_text(), reply_markup=providers_inline_keyboard())


@router.message(DDNSFSM.set_cloudflare_token)
async def process_cloudflare_token(message: types.Message, state: FSMContext) -> None:
    token = (message.text or "").strip()
    if not token:
        await message.answer("Токен пустой. Попробуйте еще раз.")
        return

    async with aiohttp.ClientSession() as session:
        result = await providers.validate_cloudflare_token(session, token)

    if not result["success"]:
        logger.warning(
            "Cloudflare token не прошел проверку: %s | admin_id=%s.",
            result["message"],
            message.from_user.id if message.from_user else "unknown",
        )
        await message.answer(f"Токен не принят: {result['message']}")
        return

    data = await state.get_data()
    account_name = data.get("provider_account_name") or db.DEFAULT_PROVIDER_ACCOUNT_NAME
    db.set_provider_account_secret(db.PROVIDER_CLOUDFLARE, token, account_name)
    logger.info(
        "Сохранен аккаунт провайдера: %s | %s | admin_id=%s.",
        provider_label(db.PROVIDER_CLOUDFLARE),
        account_name,
        message.from_user.id if message.from_user else "unknown",
    )
    await state.clear()
    await message.answer(
        f"Cloudflare-аккаунт {account_name} сохранен, токен прошел проверку.",
        reply_markup=main_reply_keyboard(),
    )
    await message.answer(build_provider_text(), reply_markup=providers_inline_keyboard())
