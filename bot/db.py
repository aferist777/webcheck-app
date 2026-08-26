"""Хранилище настроек (SQLite через aiosqlite).

Личный бот → один общий набор настроек: домены, API-ключи, включённые проверки,
интервал расписания, chat_id владельца для отправки отчётов по расписанию.
"""
from __future__ import annotations

import aiosqlite

from . import checks as checks_catalog
from .config import DB_PATH, ensure_dirs

_SCHEMA = """
CREATE TABLE IF NOT EXISTS domains (
    domain   TEXT PRIMARY KEY,
    added_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS api_keys (
    name  TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS check_toggles (
    name    TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


async def init_db() -> None:
    ensure_dirs()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(_SCHEMA)
        # Засеять состояние проверок дефолтами при первом запуске.
        cur = await db.execute("SELECT COUNT(*) FROM check_toggles")
        (count,) = await cur.fetchone()
        if count == 0:
            await db.executemany(
                "INSERT OR IGNORE INTO check_toggles(name, enabled) VALUES (?, ?)",
                [(c.name, 1 if c.default_on else 0) for c in checks_catalog.CHECKS],
            )
        else:
            # Доустановить строки для новых проверок, появившихся в каталоге.
            for c in checks_catalog.CHECKS:
                await db.execute(
                    "INSERT OR IGNORE INTO check_toggles(name, enabled) VALUES (?, ?)",
                    (c.name, 1 if c.default_on else 0),
                )
        await db.commit()


# --- Домены ---
async def add_domains(domains: list[str]) -> int:
    added = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for d in domains:
            cur = await db.execute(
                "INSERT OR IGNORE INTO domains(domain) VALUES (?)", (d,)
            )
            added += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        await db.commit()
    return added


async def remove_domain(domain: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM domains WHERE domain = ?", (domain,))
        await db.commit()
        return bool(cur.rowcount)


async def list_domains() -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT domain FROM domains ORDER BY domain")
        return [row[0] for row in await cur.fetchall()]


# --- API-ключи ---
async def set_key(name: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO api_keys(name, value) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value = excluded.value",
            (name, value),
        )
        await db.commit()


async def delete_key(name: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM api_keys WHERE name = ?", (name,))
        await db.commit()
        return bool(cur.rowcount)


async def get_keys() -> dict[str, str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, value FROM api_keys")
        return {row[0]: row[1] for row in await cur.fetchall()}


# --- Включённые проверки ---
async def get_enabled_checks() -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name FROM check_toggles WHERE enabled = 1")
        return [row[0] for row in await cur.fetchall()]


async def get_all_toggles() -> dict[str, bool]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT name, enabled FROM check_toggles")
        return {row[0]: bool(row[1]) for row in await cur.fetchall()}


async def toggle_check(name: str) -> bool:
    """Инвертирует флаг проверки, возвращает новое состояние."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT enabled FROM check_toggles WHERE name = ?", (name,)
        )
        row = await cur.fetchone()
        new_val = 0 if (row and row[0]) else 1
        await db.execute(
            "INSERT INTO check_toggles(name, enabled) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET enabled = excluded.enabled",
            (name, new_val),
        )
        await db.commit()
        return bool(new_val)


async def reset_checks_default() -> None:
    """Сбрасывает набор проверок к значениям по умолчанию."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executemany(
            "INSERT INTO check_toggles(name, enabled) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET enabled = excluded.enabled",
            [(c.name, 1 if c.default_on else 0) for c in checks_catalog.CHECKS],
        )
        await db.commit()


async def disable_all_checks() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE check_toggles SET enabled = 0")
        await db.commit()


# --- Произвольные настройки (интервал, chat_id владельца) ---
async def get_setting(key: str, default: str | None = None) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()


async def get_interval_hours() -> int:
    raw = await get_setting("interval_hours", "0")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def set_interval_hours(hours: int) -> None:
    await set_setting("interval_hours", str(hours))
