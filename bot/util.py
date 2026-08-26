"""Мелкие утилиты, общие для хендлеров."""
from __future__ import annotations

import re
from urllib.parse import urlparse


def normalize_domain(raw: str) -> str | None:
    """Приводит ввод к голому hostname или возвращает None, если непохоже на домен."""
    raw = (raw or "").strip().lower()
    if not raw:
        return None
    if "://" not in raw:
        raw = "//" + raw
    netloc = urlparse(raw).netloc
    host = netloc.split("@")[-1].split(":")[0].strip("/.")
    if not host or "." not in host or " " in host:
        return None
    return host


def parse_domains(text: str) -> list[str]:
    """Разбирает строку с доменами (через пробелы/запятые/переносы) в список валидных."""
    tokens = re.split(r"[\s,]+", (text or "").strip())
    seen, out = set(), []
    for t in tokens:
        d = normalize_domain(t)
        if d and d not in seen:
            seen.add(d)
            out.append(d)
    return out
