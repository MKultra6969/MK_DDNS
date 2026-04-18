from aiogram import types
from aiogram.exceptions import TelegramBadRequest


async def safe_edit_text(message: types.Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


async def safe_edit_menu(call: types.CallbackQuery, text: str, markup) -> None:
    await safe_edit_text(call.message, text, reply_markup=markup)
    await call.answer()
