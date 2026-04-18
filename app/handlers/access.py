from aiogram import F, Router, types

from app.config import ADMIN_ID

router = Router()


@router.message(F.from_user.id != ADMIN_ID)
async def restricted_messages(_: types.Message) -> None:
    return


@router.callback_query(F.from_user.id != ADMIN_ID)
async def restricted_callbacks(call: types.CallbackQuery) -> None:
    await call.answer()
