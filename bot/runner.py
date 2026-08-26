"""Запуск проверок и вывод по каждому домену.

Домены обрабатываются ПО ОЧЕРЕДИ (последовательно), поэтому сообщения по сайтам не
перемешиваются. По каждому домену:
  • временное статус-сообщение показывает ход проверки (в реальном времени), затем удаляется;
  • скриншot снимается параллельно с проверками;
  • итог: фото-скриншот + HTML-файл, в подписи которого — компактный отчёт со свёрнутым блоком.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import BufferedInputFile

from . import db
from . import formatting as fmt
from . import report
from . import screenshot as shot
from .config import ENGINE_DIR, NODE_BIN, RUNCHECK_JS

EDIT_INTERVAL = 1.3
_STREAM_LIMIT = 1 << 20


def _record_to_result(name: str, rec: dict) -> dict:
    status = rec.get("status")
    base = {"status": status, "ms": rec.get("ms"), "data": rec.get("data"), "error": rec.get("error")}
    if status == "ok":
        level, text = fmt.summarize(name, rec.get("data"))
    elif status == "skipped":
        data = rec.get("data") or {}
        reason = data.get("skipped") if isinstance(data, dict) else None
        level, text = "skipped", (reason or "пропущено")
    else:
        level, text = "error", (rec.get("error") or "ошибка")
    base["level"], base["text"] = level, text
    return base


def _safe_name(domain: str) -> str:
    return re.sub(r"[^a-z0-9.\-]", "_", domain.lower()) or "domain"


async def _send_results(
    bot: Bot,
    chat_id: int,
    domain: str,
    ordered: list[str],
    results: dict[str, dict],
    png: bytes | None,
    opt_html: bool,
) -> None:
    """Итоговые сообщения по домену (2 шт.: скриншот + файл с отчётом, либо комбинации)."""
    caption = fmt.render_caption_html(domain, ordered, results)
    shot_name = f"{_safe_name(domain)}.png"

    def _doc() -> BufferedInputFile:
        now = datetime.now()
        html = report.build_html(domain, ordered, results, png, now.strftime("%Y-%m-%d %H:%M"))
        fname = f"webcheck_{_safe_name(domain)}_{now.strftime('%Y%m%d-%H%M')}.html"
        return BufferedInputFile(html.encode("utf-8"), filename=fname)

    try:
        if png and opt_html:
            await bot.send_photo(
                chat_id, BufferedInputFile(png, shot_name),
                caption=f"🖼 <b>{fmt.html_escape(domain)}</b>", parse_mode=ParseMode.HTML,
            )
            await bot.send_document(chat_id, _doc(), caption=caption, parse_mode=ParseMode.HTML)
        elif png and not opt_html:
            await bot.send_photo(
                chat_id, BufferedInputFile(png, shot_name), caption=caption, parse_mode=ParseMode.HTML
            )
        elif opt_html:  # без скриншота
            await bot.send_document(chat_id, _doc(), caption=caption, parse_mode=ParseMode.HTML)
        else:  # ни фото, ни файла — полный отчёт сообщением
            await bot.send_message(
                chat_id, fmt.render_domain_html(domain, ordered, results, done=True),
                parse_mode=ParseMode.HTML,
            )
    except Exception:
        # На случай проблем с разметкой/вложением — отправим хотя бы краткий итог.
        await bot.send_message(
            chat_id, fmt.render_progress_html(domain, ordered, results), parse_mode=ParseMode.HTML
        )


async def run_domain(
    bot: Bot,
    chat_id: int,
    domain: str,
    ordered_checks: list[str],
    keys: dict[str, str],
) -> dict[str, dict]:
    """Проверяет один домен; ведёт временный статус, шлёт итоговые сообщения."""
    loop = asyncio.get_running_loop()
    results: dict[str, dict] = {}
    state = {"last_edit": 0.0, "last_text": None}

    opt_html = (await db.get_setting("opt_html", "1")) != "0"
    opt_shot = (await db.get_setting("opt_shot", "1")) != "0"

    # Скриншот снимаем параллельно с проверками.
    shot_task = (
        asyncio.create_task(shot.capture(domain))
        if (opt_shot and shot.available())
        else None
    )

    status = await bot.send_message(
        chat_id, fmt.render_progress_html(domain, ordered_checks, results), parse_mode=ParseMode.HTML
    )

    async def push(force: bool) -> None:
        now = loop.time()
        if not force and now - state["last_edit"] < EDIT_INTERVAL:
            return
        text = fmt.render_progress_html(domain, ordered_checks, results)
        if text == state["last_text"]:
            state["last_edit"] = now
            return
        try:
            await bot.edit_message_text(
                text, chat_id=chat_id, message_id=status.message_id, parse_mode=ParseMode.HTML
            )
            state["last_text"], state["last_edit"] = text, now
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramBadRequest:
            pass

    env = {**os.environ, **keys, "PLATFORM": "NODE"}
    try:
        proc = await asyncio.create_subprocess_exec(
            NODE_BIN, str(RUNCHECK_JS), domain, ",".join(ordered_checks),
            cwd=str(ENGINE_DIR), env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=_STREAM_LIMIT,
        )
    except FileNotFoundError:
        results["_"] = {"level": "error", "text": f"не найден node ({NODE_BIN})", "status": "error"}
        png = await shot_task if shot_task else None
        await _send_results(bot, chat_id, domain, ordered_checks, results, png, opt_html)
        try:
            await bot.delete_message(chat_id, status.message_id)
        except Exception:
            pass
        return results

    stderr_task = asyncio.create_task(proc.stderr.read())
    async for raw in proc.stdout:
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = rec.get("check")
        if not name:
            continue
        results[name] = _record_to_result(name, rec)
        await push(force=False)

    await proc.wait()
    stderr = (await stderr_task).decode("utf-8", "replace").strip()

    for name in ordered_checks:
        results.setdefault(name, {"level": "error", "text": "нет ответа", "status": "error", "error": "нет ответа"})
    if not any(r.get("level") != "error" for r in results.values()) and stderr:
        results["_"] = {"level": "error", "text": stderr.splitlines()[0][:160], "status": "error"}

    await push(force=True)

    png = None
    if shot_task:
        try:
            png = await shot_task
        except Exception:
            png = None

    await _send_results(bot, chat_id, domain, ordered_checks, results, png, opt_html)
    try:
        await bot.delete_message(chat_id, status.message_id)
    except Exception:
        pass
    return results


async def run_batch(
    bot: Bot,
    chat_id: int,
    domains: list[str],
    checks: list[str],
    keys: dict[str, str],
    *,
    lead: bool = True,
) -> dict[str, dict[str, dict]]:
    """Последовательный прогон доменов: по одному сайту за раз, сообщения не перемешиваются."""
    if lead:
        await bot.send_message(
            chat_id,
            fmt.esc(f"🚀 Запускаю проверку: {len(domains)} дом. × {len(checks)} проверок (по очереди)"),
        )
    report_map: dict[str, dict[str, dict]] = {}
    for d in domains:
        try:
            report_map[d] = await run_domain(bot, chat_id, d, checks, keys)
        except Exception as e:  # один домен не должен ронять весь прогон
            report_map[d] = {"_": {"level": "error", "text": str(e), "status": "error"}}
            try:
                await bot.send_message(chat_id, fmt.esc(f"❌ {d}: {e}"))
            except Exception:
                pass
    return report_map
