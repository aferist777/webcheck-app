"""Inline-меню: навигация по разделам, пояснения и ввод данных кнопками."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import db, keyboards as kb, scheduler
from .. import formatting as fmt
from .. import screenshot as shot
from ..checks import BY_NAME, KEY_ENV_NAMES
from ..runner import run_batch
from ..util import parse_domains

router = Router()
E = fmt.esc


def _b(t: object) -> str:
    return f"*{E(t)}*"


def _c(t: object) -> str:
    # В code-span MarkdownV2 экранируются только обратный апостроф и бэкслеш.
    s = str(t).replace("\\", "\\\\").replace("`", "\\`")
    return f"`{s}`"


class Flow(StatesGroup):
    add_domains = State()
    set_key = State()


def _interval_label(h: int) -> str:
    return "выключено" if not h else f"каждые {h} ч"


# ----------------------- рендер разделов -----------------------
async def render_main() -> tuple[str, object]:
    text = "\n".join(
        [
            "🛡 " + _b("Web-Check бот"),
            "",
            E("Проверяю домены движком web-check и присылаю отчёт в реальном времени."),
            E("Выберите раздел кнопками ниже."),
        ]
    )
    return text, kb.main_menu()


async def render_domains() -> tuple[str, object]:
    domains = await db.list_domains()
    lines = [
        "🌐 " + _b("Домены"),
        "",
        E("Список доменов, которые проверяет бот."),
        "",
    ]
    if domains:
        lines.append(_b(f"Всего: {len(domains)}"))
        lines += [f"• {_c(d)}" for d in domains]
    else:
        lines.append(E("Список пуст."))
    lines += [
        "",
        E("➕ Добавить — пришлите домены одним сообщением (через пробел, запятую или с новой строки)."),
        E("➖ Удалить — выберите домен из списка."),
    ]
    return "\n".join(lines), kb.domains_menu(bool(domains))


async def render_domains_delete() -> tuple[str, object]:
    domains = await db.list_domains()
    if not domains:
        return await render_domains()
    text = "\n".join(["🗑 " + _b("Удаление доменов"), "", E("Нажмите на домен, чтобы удалить его.")])
    return text, kb.domains_delete_menu(domains)


async def render_checks() -> tuple[str, object]:
    toggles = await db.get_all_toggles()
    enabled = sum(1 for v in toggles.values() if v)
    text = "\n".join(
        [
            "🧪 " + _b("Проверки"),
            "",
            _b(f"Включено: {enabled} из {len(toggles)}"),
            "",
            E("Нажмите на проверку, чтобы включить/выключить её."),
            E("🔑 — нужен API-ключ (см. раздел «API-ключи»)."),
            E("🌐 — нужен браузер Chromium (по умолчанию выключено)."),
        ]
    )
    return text, kb.checks_menu(toggles)


async def render_keys() -> tuple[str, object]:
    keys = await db.get_keys()
    lines = [
        "🔑 " + _b("API-ключи"),
        "",
        E("Некоторым проверкам нужен ключ. Без него такие проверки помечаются «пропущено»."),
        "",
    ]
    for env in KEY_ENV_NAMES:
        is_set = env in keys
        lines.append(f"{_c(env)} — {E('✅ задан' if is_set else '— не задан')}")
    lines += [
        "",
        E("➕ — задать значение ключа (сообщение с секретом будет удалено)."),
        E("🗑 — удалить ключ."),
    ]
    return "\n".join(lines), kb.keys_menu(keys)


async def render_interval() -> tuple[str, object]:
    hours = await db.get_interval_hours()
    nrt = scheduler.next_run_time()
    nrt_s = nrt.strftime("%Y-%m-%d %H:%M") if nrt else "—"
    text = "\n".join(
        [
            "⏱ " + _b("Периодичность"),
            "",
            f"{E('Текущая:')} {_b(_interval_label(hours))}",
            f"{E('Следующий запуск:')} {E(nrt_s)}",
            "",
            E("Бот будет автоматически проверять все домены с выбранным интервалом и присылать отчёт."),
        ]
    )
    return text, kb.interval_menu(hours)


async def render_run() -> tuple[str, object]:
    domains = await db.list_domains()
    checks = await db.get_enabled_checks()
    lines = ["▶️ " + _b("Запуск проверки"), ""]
    can = bool(domains and checks)
    if not domains:
        lines.append(E("⚠️ Нет доменов. Добавьте их в разделе «Домены»."))
    elif not checks:
        lines.append(E("⚠️ Нет активных проверок. Включите их в разделе «Проверки»."))
    else:
        lines.append(E(f"Будет проверено: {len(domains)} доменов × {len(checks)} проверок."))
        lines.append(E("На каждый домен — отдельное сообщение, обновляемое в реальном времени."))
    return "\n".join(lines), kb.run_menu(can)


async def render_status() -> tuple[str, object]:
    domains = await db.list_domains()
    enabled = await db.get_enabled_checks()
    hours = await db.get_interval_hours()
    keys = await db.get_keys()
    nrt = scheduler.next_run_time()
    nrt_s = nrt.strftime("%Y-%m-%d %H:%M") if nrt else "—"
    text = "\n".join(
        [
            "📊 " + _b("Статус"),
            "",
            f"{E('Доменов:')} {_b(len(domains))}",
            f"{E('Активных проверок:')} {_b(len(enabled))}",
            f"{E('Периодичность:')} {_b(_interval_label(hours))}",
            f"{E('Следующий запуск:')} {E(nrt_s)}",
            f"{E('Ключей задано:')} {_b(len(keys))}",
        ]
    )
    return text, kb.status_menu()


async def render_help() -> tuple[str, object]:
    text = "\n".join(
        [
            "❓ " + _b("Как пользоваться"),
            "",
            E("1. «Домены» — добавьте сайты для проверки."),
            E("2. «Проверки» — выберите, что проверять (по умолчанию включён безопасный набор)."),
            E("3. «API-ключи» — по желанию задайте ключи для Shodan/Google."),
            E("4. «Запустить проверку» — получите отчёт в реальном времени."),
            E("5. «Периодичность» — включите автопроверки по расписанию."),
            "",
            E("Команды-ярлыки: /menu, /run, /status, /add, /setkey."),
        ]
    )
    return text, kb.simple_back()


async def render_report() -> tuple[str, object]:
    opt_html = (await db.get_setting("opt_html", "1")) != "0"
    opt_shot = (await db.get_setting("opt_shot", "1")) != "0"
    avail = shot.available()
    lines = [
        "📄 " + _b("Отчёт"),
        "",
        E("Что прикладывать к результату по каждому домену:"),
        "",
        f"{E('• HTML-отчёт:')} {_b('вкл' if opt_html else 'выкл')}",
        E("  подробный документ с пояснениями по каждой проверке."),
        f"{E('• Скриншот:')} {_b('вкл' if opt_shot else 'выкл')}",
        E("  снимок главной страницы сайта."),
    ]
    if not avail:
        lines += ["", E("⚠️ Скриншоты недоступны: не найден Chrome/Edge в системе.")]
    lines += ["", E("Сами результаты всегда приходят сообщением со свёрнутыми деталями.")]
    return "\n".join(lines), kb.report_menu(opt_html, opt_shot, avail)


RENDER = {
    "main": render_main,
    "domains": render_domains,
    "checks": render_checks,
    "keys": render_keys,
    "interval": render_interval,
    "run": render_run,
    "report": render_report,
    "status": render_status,
    "help": render_help,
}


# ----------------------- помощники -----------------------
async def _edit(cq: CallbackQuery, text: str, markup) -> None:
    try:
        await cq.message.edit_text(text, reply_markup=markup)
    except Exception:
        # «message is not modified» и подобные — не критично.
        pass


async def _open(message: Message, section: str) -> None:
    text, markup = await RENDER[section]()
    await message.answer(text, reply_markup=markup)


# ----------------------- команды -----------------------
@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await db.set_setting("owner_chat_id", str(message.chat.id))
    await _open(message, "main")


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    await _open(message, "status")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await _open(message, "help")


@router.message(Command("run", "check"))
async def cmd_run(message: Message) -> None:
    await db.set_setting("owner_chat_id", str(message.chat.id))
    await _open(message, "run")


@router.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject) -> None:
    valid = parse_domains(command.args or "")
    if not valid:
        await message.answer(E("Использование: /add example.com github.com"))
        return
    added = await db.add_domains(valid)
    await message.answer(E(f"➕ Добавлено: {added}. Всего: {len(await db.list_domains())}"))


@router.message(Command("setkey"))
async def cmd_setkey(message: Message, command: CommandObject) -> None:
    parts = (command.args or "").split()
    if len(parts) < 2:
        await message.answer(E("Использование: /setkey SHODAN_API_KEY значение"))
        return
    await db.set_key(parts[0].upper(), " ".join(parts[1:]).strip())
    try:
        await message.delete()
    except Exception:
        pass
    await message.answer(E(f"🔑 Ключ {parts[0].upper()} сохранён. Сообщение удалено."))


# ----------------------- навигация (m:*) -----------------------
@router.callback_query(F.data.startswith("m:"))
async def cb_nav(cq: CallbackQuery, state: FSMContext) -> None:
    section = cq.data.split(":", 1)[1]
    if section in ("main", "cancel"):
        await state.clear()
        section = "main"
    text, markup = await RENDER[section]()
    await _edit(cq, text, markup)
    await cq.answer()


# ----------------------- домены -----------------------
@router.callback_query(F.data == "dom:add")
async def cb_dom_add(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.add_domains)
    text = "\n".join(
        [
            "➕ " + _b("Добавление доменов"),
            "",
            E("Пришлите один или несколько доменов одним сообщением."),
            E("Можно через пробел, запятую или с новой строки. Например:"),
            _c("example.com github.com t.me"),
        ]
    )
    await _edit(cq, text, kb.cancel_kb())
    await cq.answer()


@router.callback_query(F.data == "dom:del")
async def cb_dom_del(cq: CallbackQuery) -> None:
    text, markup = await render_domains_delete()
    await _edit(cq, text, markup)
    await cq.answer()


@router.callback_query(F.data.startswith("dd:"))
async def cb_dom_delete_one(cq: CallbackQuery) -> None:
    domain = cq.data.split(":", 1)[1]
    await db.remove_domain(domain)
    text, markup = await render_domains_delete()
    await _edit(cq, text, markup)
    await cq.answer(f"Удалён: {domain}")


@router.message(Flow.add_domains, F.text)
async def on_add_domains(message: Message, state: FSMContext) -> None:
    valid = parse_domains(message.text)
    if not valid:
        await message.answer(E("Не распознал домены. Пришлите ещё раз или нажмите «Отмена»."))
        return
    added = await db.add_domains(valid)
    await state.clear()
    await message.answer(E(f"➕ Добавлено новых: {added} (из {len(valid)})."))
    await _open(message, "domains")


# ----------------------- проверки -----------------------
@router.callback_query(F.data.startswith("tg:"))
async def cb_toggle(cq: CallbackQuery) -> None:
    name = cq.data.split(":", 1)[1]
    if name not in BY_NAME:
        await cq.answer("неизвестная проверка")
        return
    state_on = await db.toggle_check(name)
    text, markup = await render_checks()
    await _edit(cq, text, markup)
    await cq.answer("включено" if state_on else "выключено")


@router.callback_query(F.data == "chk:default")
async def cb_checks_default(cq: CallbackQuery) -> None:
    await db.reset_checks_default()
    text, markup = await render_checks()
    await _edit(cq, text, markup)
    await cq.answer("Сброшено к умолчанию")


@router.callback_query(F.data == "chk:none")
async def cb_checks_none(cq: CallbackQuery) -> None:
    await db.disable_all_checks()
    text, markup = await render_checks()
    await _edit(cq, text, markup)
    await cq.answer("Все выключены")


# ----------------------- ключи -----------------------
@router.callback_query(F.data.startswith("key:set:"))
async def cb_key_set(cq: CallbackQuery, state: FSMContext) -> None:
    env = cq.data.split(":", 2)[2]
    await state.set_state(Flow.set_key)
    await state.update_data(env=env)
    text = "\n".join(
        [
            "🔑 " + _b(env),
            "",
            E("Пришлите значение ключа одним сообщением."),
            E("Оно будет сохранено, а ваше сообщение — удалено."),
        ]
    )
    await _edit(cq, text, kb.cancel_kb())
    await cq.answer()


@router.callback_query(F.data.startswith("key:del:"))
async def cb_key_del(cq: CallbackQuery) -> None:
    env = cq.data.split(":", 2)[2]
    await db.delete_key(env)
    text, markup = await render_keys()
    await _edit(cq, text, markup)
    await cq.answer(f"{env} удалён")


@router.message(Flow.set_key, F.text)
async def on_set_key(message: Message, state: FSMContext) -> None:
    if message.text.startswith("/"):
        await message.answer(E("Это команда. Пришлите значение ключа или нажмите «Отмена»."))
        return
    data = await state.get_data()
    env = data.get("env")
    await db.set_key(env, message.text.strip())
    try:
        await message.delete()
    except Exception:
        pass
    await state.clear()
    await message.answer(E(f"🔑 Ключ {env} сохранён. Сообщение с секретом удалено."))
    await _open(message, "keys")


# ----------------------- периодичность -----------------------
@router.callback_query(F.data.startswith("iv:"))
async def cb_interval(cq: CallbackQuery) -> None:
    hours = int(cq.data.split(":", 1)[1])
    await db.set_interval_hours(hours)
    scheduler.apply_interval(hours)
    text, markup = await render_interval()
    await _edit(cq, text, markup)
    await cq.answer("Сохранено")


# ----------------------- отчёт (вложения) -----------------------
@router.callback_query(F.data.in_({"opt:html", "opt:shot"}))
async def cb_report_opt(cq: CallbackQuery) -> None:
    key = "opt_html" if cq.data == "opt:html" else "opt_shot"
    cur = (await db.get_setting(key, "1")) != "0"
    await db.set_setting(key, "0" if cur else "1")
    text, markup = await render_report()
    await _edit(cq, text, markup)
    await cq.answer("Выключено" if cur else "Включено")


# ----------------------- запуск -----------------------
@router.callback_query(F.data == "run:go")
async def cb_run(cq: CallbackQuery) -> None:
    domains = await db.list_domains()
    checks = await db.get_enabled_checks()
    if not domains or not checks:
        await cq.answer("Нет доменов или проверок", show_alert=True)
        return
    await cq.answer("Запускаю…")
    chat_id = cq.message.chat.id
    await db.set_setting("owner_chat_id", str(chat_id))
    await _edit(
        cq,
        E(f"🚀 Запускаю: {len(domains)} доменов × {len(checks)} проверок…"),
        None,
    )
    keys = await db.get_keys()
    await run_batch(cq.bot, chat_id, domains, checks, keys, lead=False)
    text, markup = await render_main()
    await cq.message.answer("✅ " + E("Проверка завершена.") + "\n\n" + text, reply_markup=markup)
