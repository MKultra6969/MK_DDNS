import asyncio
import logging

from aiogram import Bot, Dispatcher

from app import db
from app.config import TOKEN
from app.handlers import access_router, menu_router, providers_router, records_router
from app.services.ddns import ddns_loop

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, force=True)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


def build_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(access_router)
    dispatcher.include_router(menu_router)
    dispatcher.include_router(providers_router)
    dispatcher.include_router(records_router)
    return dispatcher


async def main() -> None:
    configure_logging()
    db.init_db()
    bot = Bot(token=TOKEN)
    dispatcher = build_dispatcher()
    asyncio.create_task(ddns_loop(bot))
    await dispatcher.start_polling(bot)
