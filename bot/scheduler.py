"""Планировщик периодических проверок (APScheduler, asyncio)."""
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot

from . import db
from . import formatting as fmt
from .runner import run_batch

JOB_ID = "periodic-scan"

_scheduler: AsyncIOScheduler | None = None
_bot: Bot | None = None


async def _scheduled_run() -> None:
    if _bot is None:
        return
    domains = await db.list_domains()
    checks = await db.get_enabled_checks()
    chat_raw = await db.get_setting("owner_chat_id")
    if not domains or not checks or not chat_raw:
        return
    chat_id = int(chat_raw)
    keys = await db.get_keys()
    await _bot.send_message(chat_id, fmt.esc("⏰ Проверка по расписанию"))
    await run_batch(_bot, chat_id, domains, checks, keys, lead=False)


def setup(bot: Bot) -> None:
    """Создаёт и запускает планировщик (вызывать внутри работающего event loop)."""
    global _scheduler, _bot
    _bot = bot
    _scheduler = AsyncIOScheduler()
    _scheduler.start()


def apply_interval(hours: int) -> None:
    """Переустанавливает интервальный job. hours<=0 — выключить."""
    if _scheduler is None:
        return
    existing = _scheduler.get_job(JOB_ID)
    if existing:
        existing.remove()
    if hours and hours > 0:
        _scheduler.add_job(
            _scheduled_run,
            IntervalTrigger(hours=hours),
            id=JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )


async def restore() -> None:
    """Восстанавливает расписание из БД при старте."""
    apply_interval(await db.get_interval_hours())


def next_run_time():
    if _scheduler is None:
        return None
    job = _scheduler.get_job(JOB_ID)
    return job.next_run_time if job else None
