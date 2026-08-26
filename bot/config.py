"""Конфигурация бота: читается из .env (в git не коммитится)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Корень проекта = родитель пакета bot/
ROOT_DIR = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT_DIR / "engine"
RUNCHECK_JS = ENGINE_DIR / "runcheck.mjs"
SCREENSHOT_JS = ENGINE_DIR / "screenshot.mjs"
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "config.db"

load_dotenv(ROOT_DIR / ".env")


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


# Токен бота — обязателен (берётся ТОЛЬКО из окружения, в коде не хранится).
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "").strip()

# Владелец и доверенные пользователи (whitelist по Telegram user id).
OWNER_ID: int | None = _int_or_none(os.environ.get("OWNER_ID"))
_extra = os.environ.get("EXTRA_WHITELIST", "")
EXTRA_WHITELIST: set[int] = {
    int(x) for x in _extra.replace(";", ",").split(",") if x.strip().isdigit()
}
WHITELIST: set[int] = ({OWNER_ID} if OWNER_ID else set()) | EXTRA_WHITELIST

# Путь к node (можно переопределить, если не в PATH).
NODE_BIN: str = os.environ.get("NODE_BIN", "node")

# Параллельность по доменам в одном прогоне.
DOMAIN_CONCURRENCY: int = int(os.environ.get("DOMAIN_CONCURRENCY", "4"))

# Доступные пресеты интервалов (часы). 0 = выключено.
INTERVAL_PRESETS: tuple[int, ...] = (6, 12, 24)


def find_browser() -> str | None:
    """Путь к системному Chrome/Edge для скриншотов (или None)."""
    override = os.environ.get("BROWSER_PATH")
    if override and Path(override).exists():
        return override
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LocalAppData", "")
    candidates = [
        rf"{pf}\Google\Chrome\Application\chrome.exe",
        rf"{pfx86}\Google\Chrome\Application\chrome.exe",
        rf"{local}\Google\Chrome\Application\chrome.exe",
        rf"{pf}\Microsoft\Edge\Application\msedge.exe",
        rf"{pfx86}\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def validate() -> list[str]:
    """Возвращает список проблем конфигурации (пусто = всё ок)."""
    problems: list[str] = []
    if not BOT_TOKEN:
        problems.append("BOT_TOKEN не задан в .env")
    if not WHITELIST:
        problems.append("OWNER_ID не задан в .env (некому пользоваться ботом)")
    if not RUNCHECK_JS.exists():
        problems.append(f"Не найден раннер движка: {RUNCHECK_JS}")
    return problems
