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
    await state.set_state(DDNSFSM.set_1984_key)
    await call.answer()
    await call.message.answer(
        "Отправьте API key от 1984Hosting одним сообщением.",
        reply_markup=back_to_providers_keyboard(),
    )


@router.callback_query(F.data == "provider:set:cloudflare")
async def provider_set_cloudflare(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(DDNSFSM.set_cloudflare_token)
    await call.answer()
    await call.message.answer(
        "Отправьте Cloudflare API token.\nНужны права Zone:Read и DNS:Edit.",
        reply_markup=back_to_providers_keyboard(),
    )


@router.message(DDNSFSM.set_1984_key)
async def process_1984_key(message: types.Message, state: FSMContext) -> None:
    secret = (message.text or "").strip()
    if not secret:
        await message.answer("API key пустой. Попробуйте еще раз.")
        return

    db.set_provider_secret(db.PROVIDER_1984, secret)
    logger.info(
        "Сохранены настройки провайдера: %s | admin_id=%s.",
        provider_label(db.PROVIDER_1984),
        message.from_user.id if message.from_user else "unknown",
    )
    await state.clear()
    await message.answer("API key 1984Hosting сохранен.", reply_markup=main_reply_keyboard())
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

    db.set_provider_secret(db.PROVIDER_CLOUDFLARE, token)
    logger.info(
        "Сохранены настройки провайдера: %s | admin_id=%s.",
        provider_label(db.PROVIDER_CLOUDFLARE),
        message.from_user.id if message.from_user else "unknown",
    )
    await state.clear()
    await message.answer(
        "Cloudflare token сохранен и прошел проверку.",
        reply_markup=main_reply_keyboard(),
    )
    await message.answer(build_provider_text(), reply_markup=providers_inline_keyboard())
