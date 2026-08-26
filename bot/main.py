"""Точка входа бота: настройка диспетчера, middleware, планировщика, long polling."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from . import config, db, scheduler
from .access import WhitelistMiddleware
from .handlers import routers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("webcheck-bot")

COMMANDS = [
    BotCommand(command="menu", description="Открыть меню"),
    BotCommand(command="run", description="Запустить проверку"),
    BotCommand(command="status", description="Текущие настройки"),
    BotCommand(command="add", description="Быстро добавить домены"),
    BotCommand(command="setkey", description="Задать API-ключ"),
    BotCommand(command="help", description="Как пользоваться"),
]


async def main() -> None:
    problems = config.validate()
    if problems:
        for p in problems:
            log.error("Конфигурация: %s", p)
        if not config.BOT_TOKEN or not config.WHITELIST:
            log.error("Старт невозможен. Заполните .env (см. .env.example).")
            return

    await db.init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.MARKDOWN_V2,
            link_preview_is_disabled=True,
        ),
    )
    dp = Dispatcher()

    # Доступ только для whitelist (на сообщениях и колбэках).
    dp.message.outer_middleware(WhitelistMiddleware())
    dp.callback_query.outer_middleware(WhitelistMiddleware())

    for r in routers:
        dp.include_router(r)

    scheduler.setup(bot)
    await scheduler.restore()

    await bot.set_my_commands(COMMANDS)

    me = await bot.get_me()
    log.info("Бот @%s запущен. Whitelist: %s", me.username, sorted(config.WHITELIST))
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
