"""Сборка inline-клавиатур для меню."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .checks import CHECKS, KEY_ENV_NAMES
from .config import INTERVAL_PRESETS


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _rows(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[r for r in rows if r])


BACK_MAIN = "m:main"


def back_row(target: str = BACK_MAIN) -> list[InlineKeyboardButton]:
    return [_btn("⬅️ В меню", target)]


def main_menu() -> InlineKeyboardMarkup:
    return _rows(
        [_btn("🌐 Домены", "m:domains"), _btn("🧪 Проверки", "m:checks")],
        [_btn("🔑 API-ключи", "m:keys"), _btn("⏱ Периодичность", "m:interval")],
        [_btn("▶️ Запустить проверку", "m:run")],
        [_btn("📄 Отчёт", "m:report"), _btn("📊 Статус", "m:status")],
        [_btn("❓ Помощь", "m:help")],
    )


def report_menu(opt_html: bool, opt_shot: bool, shot_available: bool) -> InlineKeyboardMarkup:
    html_mark = "✅" if opt_html else "⬜"
    shot_mark = ("✅" if opt_shot else "⬜") if shot_available else "🚫"
    return _rows(
        [_btn(f"{html_mark} HTML-отчёт", "opt:html")],
        [_btn(f"{shot_mark} Скриншот", "opt:shot")],
        back_row(),
    )


def cancel_kb() -> InlineKeyboardMarkup:
    return _rows([_btn("✖️ Отмена", "m:cancel")])


def domains_menu(has_domains: bool) -> InlineKeyboardMarkup:
    top = [_btn("➕ Добавить", "dom:add")]
    if has_domains:
        top.append(_btn("➖ Удалить", "dom:del"))
    return _rows(top, back_row())


def domains_delete_menu(domains: list[str]) -> InlineKeyboardMarkup:
    rows = [[_btn(f"🗑 {d}", f"dd:{d}")] for d in domains]
    rows.append([_btn("⬅️ Назад", "m:domains")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def checks_menu(toggles: dict[str, bool]) -> InlineKeyboardMarkup:
    rows, row = [], []
    for c in CHECKS:
        on = toggles.get(c.name, c.default_on)
        mark = "✅" if on else "⬜"
        suffix = " 🔑" if c.needs_key else (" 🌐" if c.browser else "")
        row.append(_btn(f"{mark} {c.title}{suffix}", f"tg:{c.name}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_btn("↩️ По умолчанию", "chk:default"), _btn("⬜ Снять все", "chk:none")])
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def keys_menu(keys: dict[str, str]) -> InlineKeyboardMarkup:
    rows = []
    for env in KEY_ENV_NAMES:
        is_set = env in keys
        label = f"{'✅' if is_set else '➕'} {env}"
        row = [_btn(label, f"key:set:{env}")]
        if is_set:
            row.append(_btn("🗑", f"key:del:{env}"))
        rows.append(row)
    # ключи, заданные вручную сверх известных
    for env in keys:
        if env not in KEY_ENV_NAMES:
            rows.append([_btn(f"✅ {env}", f"key:set:{env}"), _btn("🗑", f"key:del:{env}")])
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def interval_menu(current: int) -> InlineKeyboardMarkup:
    row = []
    for h in INTERVAL_PRESETS:
        mark = "✓ " if current == h else ""
        row.append(_btn(f"{mark}{h} ч", f"iv:{h}"))
    row.append(_btn(("✓ " if current == 0 else "") + "Выкл", "iv:0"))
    return _rows(row, back_row())


def run_menu(can_run: bool) -> InlineKeyboardMarkup:
    rows = []
    if can_run:
        rows.append([_btn("🚀 Запустить сейчас", "run:go")])
    rows.append(back_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def status_menu() -> InlineKeyboardMarkup:
    return _rows([_btn("🔄 Обновить", "m:status")], back_row())


def simple_back() -> InlineKeyboardMarkup:
    return _rows(back_row())
