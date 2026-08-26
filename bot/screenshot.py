"""Снимок страницы системным Chrome/Edge через engine/screenshot.mjs."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from .config import ENGINE_DIR, NODE_BIN, SCREENSHOT_JS, find_browser


def _full_url(domain: str) -> str:
    d = domain.strip()
    return d if "://" in d else f"https://{d}"


async def capture(domain: str, timeout: float = 35.0) -> bytes | None:
    """Возвращает PNG-байты скриншота или None (если браузер недоступен/ошибка)."""
    exe = find_browser()
    if not exe or not SCREENSHOT_JS.exists():
        return None

    tmp = Path(tempfile.gettempdir()) / f"wc_shot_{abs(hash(domain)) % 10_000_000}.png"
    try:
        proc = await asyncio.create_subprocess_exec(
            NODE_BIN,
            str(SCREENSHOT_JS),
            _full_url(domain),
            str(tmp),
            exe,
            cwd=str(ENGINE_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return None
        if proc.returncode == 0 and tmp.exists():
            return tmp.read_bytes()
        return None
    except (FileNotFoundError, OSError):
        return None
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def available() -> bool:
    return bool(find_browser()) and SCREENSHOT_JS.exists()
