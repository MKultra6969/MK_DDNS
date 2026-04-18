from aiogram import F, Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

from app import db
from app.services.ddns import perform_ddns_update
from app.ui import (
    back_to_records_keyboard,
    build_main_text,
    build_provider_text,
    build_records_text,
    build_status_text,
    main_inline_keyboard,
    main_reply_keyboard,
    providers_inline_keyboard,
    records_inline_keyboard,
    records_list_keyboard,
    safe_edit_menu,
    safe_edit_text,
)

router = Router()


async def show_main_menu_message(message: types.Message) -> None:
    await message.answer(build_main_text(), reply_markup=main_inline_keyboard())


@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(build_main_text(), reply_markup=main_reply_keyboard())
    await show_main_menu_message(message)


@router.message(Command("menu"))
@router.message(F.text == "Главное меню")
async def cmd_menu(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(build_main_text(), reply_markup=main_reply_keyboard())
    await show_main_menu_message(message)


@router.message(Command("providers"))
@router.message(F.text == "Провайдеры")
async def cmd_providers(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(build_provider_text(), reply_markup=providers_inline_keyboard())


@router.message(Command("records"))
@router.message(Command("add"))
@router.message(F.text == "Записи")
async def cmd_records(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(build_records_text(db.list_records()), reply_markup=records_inline_keyboard())


@router.message(Command("status"))
@router.message(F.text == "Статус")
async def cmd_status(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(build_status_text(), reply_markup=main_inline_keyboard())


@router.message(Command("list"))
async def cmd_list(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    records = db.list_records()
    markup = records_list_keyboard(records) if records else back_to_records_keyboard()
    await message.answer(build_records_text(records), reply_markup=markup)


@router.message(Command("check"))
@router.message(F.text == "Обновить сейчас")
async def cmd_check(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    status_message = await message.answer("Запускаю обновление всех записей...")
    report = await perform_ddns_update(force=True)
    await status_message.delete()
    await message.answer(report or "IP не изменился.", reply_markup=main_inline_keyboard())


@router.message(Command("cancel"))
@router.message(F.text == "Отмена ввода")
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Текущий ввод отменен.", reply_markup=main_reply_keyboard())
    await show_main_menu_message(message)


@router.callback_query(F.data == "menu:home")
async def menu_home(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit_menu(call, build_main_text(), main_inline_keyboard())


@router.callback_query(F.data == "menu:providers")
async def menu_providers(call: types.CallbackQuery) -> None:
    await safe_edit_menu(call, build_provider_text(), providers_inline_keyboard())


@router.callback_query(F.data == "menu:records")
async def menu_records(call: types.CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await safe_edit_menu(call, build_records_text(db.list_records()), records_inline_keyboard())


@router.callback_query(F.data == "menu:status")
async def menu_status(call: types.CallbackQuery) -> None:
    await safe_edit_menu(call, build_status_text(), main_inline_keyboard())


@router.callback_query(F.data == "menu:check")
async def menu_check(call: types.CallbackQuery) -> None:
    await call.answer("Обновляю записи...")
    await safe_edit_text(call.message, "Запускаю обновление всех записей...")
    report = await perform_ddns_update(force=True)
    await safe_edit_text(
        call.message,
        report or "IP не изменился.",
        reply_markup=main_inline_keyboard(),
    )
