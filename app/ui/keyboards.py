from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app import db


def main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Провайдеры"), KeyboardButton(text="Записи")],
            [KeyboardButton(text="Статус"), KeyboardButton(text="Обновить сейчас")],
            [KeyboardButton(text="Главное меню"), KeyboardButton(text="Отмена ввода")],
        ],
        resize_keyboard=True,
    )


def main_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Провайдеры", callback_data="menu:providers"),
                InlineKeyboardButton(text="Записи", callback_data="menu:records"),
            ],
            [
                InlineKeyboardButton(text="Статус", callback_data="menu:status"),
                InlineKeyboardButton(text="Обновить", callback_data="menu:check"),
            ],
        ]
    )


def providers_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Добавить 1984Hosting",
                    callback_data="provider:add:1984",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Добавить Cloudflare",
                    callback_data="provider:add:cloudflare",
                )
            ],
            [InlineKeyboardButton(text="Назад", callback_data="menu:home")],
        ]
    )


def records_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Добавить 1984Hosting", callback_data="records:add:1984")],
            [InlineKeyboardButton(text="Добавить Cloudflare", callback_data="records:add:cloudflare")],
            [InlineKeyboardButton(text="Показать записи", callback_data="records:list")],
            [InlineKeyboardButton(text="Назад", callback_data="menu:home")],
        ]
    )


def back_to_records_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="К записям", callback_data="menu:records")],
            [InlineKeyboardButton(text="Главное меню", callback_data="menu:home")],
        ]
    )


def back_to_providers_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="К провайдерам", callback_data="menu:providers")],
            [InlineKeyboardButton(text="Главное меню", callback_data="menu:home")],
        ]
    )


def provider_accounts_inline_keyboard(
    accounts: list[dict],
    *,
    callback_prefix: str,
    back_callback: str = "menu:records",
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{account['name']}",
                callback_data=f"{callback_prefix}:{account['id']}",
            )
        ]
        for account in accounts
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def zone_inline_keyboard(zones: list[dict[str, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=zone["name"], callback_data=f"cfzone:{index}")]
        for index, zone in enumerate(zones)
    ]
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu:records")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def proxied_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Cloudflare proxy", callback_data="cfproxy:1"),
                InlineKeyboardButton(text="Только DNS", callback_data="cfproxy:0"),
            ],
            [InlineKeyboardButton(text="Отмена", callback_data="menu:records")],
        ]
    )


def delete_confirm_keyboard(record_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Удалить", callback_data=f"record:confirm_delete:{record_id}"),
                InlineKeyboardButton(text="Назад", callback_data="records:list"),
            ]
        ]
    )


def records_list_keyboard(records: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for record in records:
        icon = "☁️" if record["provider"] == db.PROVIDER_CLOUDFLARE else "🌐"
        account_name = record.get("provider_account_name") or "?"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} Удалить #{record['id']} {account_name}: {record['domain']}",
                    callback_data=f"record:delete:{record['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="Назад", callback_data="menu:records")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
