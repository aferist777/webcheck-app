"""Каталог проверок web-check: имя модуля -> метаданные.

`name` совпадает с именем файла в engine/api/<name>.js.
`needs_key` — имя env-переменной с API-ключом (или None).
`browser` — нужен Chromium (по умолчанию выключено, на Windows обычно недоступно).
`default_on` — входит ли в набор по умолчанию.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    name: str
    title: str  # короткая подпись для UI/отчёта
    default_on: bool = False
    needs_key: str | None = None
    browser: bool = False
    note: str = ""


CHECKS: tuple[Check, ...] = (
    # --- Набор по умолчанию: быстрые, без ключей и браузера ---
    Check("dns", "DNS-записи", default_on=True),
    Check("get-ip", "IP-адрес", default_on=True),
    Check("ssl", "SSL-сертификат", default_on=True),
    Check("tls-connection", "TLS-соединение", default_on=True),
    Check("http-security", "Security-заголовки", default_on=True),
    Check("headers", "HTTP-заголовки", default_on=True),
    Check("hsts", "HSTS", default_on=True),
    Check("security-txt", "security.txt", default_on=True),
    Check("redirects", "Редиректы", default_on=True),
    Check("robots-txt", "robots.txt", default_on=True),
    Check("sitemap", "Sitemap", default_on=True),
    Check("whois", "WHOIS", default_on=True),
    Check("dnssec", "DNSSEC", default_on=True),
    Check("social-tags", "Соц. теги", default_on=True),
    Check("status", "Доступность", default_on=True),
    Check("mail-config", "Почтовые записи", default_on=True),
    Check("txt-records", "TXT-записи", default_on=True),
    Check("ports", "Открытые порты", default_on=True),
    Check("dns-server", "DNS-серверы", default_on=True),
    Check("firewall", "WAF / Firewall", default_on=True),
    Check("location", "Геолокация IP", default_on=True),
    # --- Доступны, но по умолчанию выключены (внешние API / медленно) ---
    Check("cookies", "Cookies", browser=True, note="нужен Chromium"),
    Check("carbon", "Углеродный след", note="внешний API"),
    Check("rank", "Рейтинг сайта", note="внешний API"),
    Check("archives", "Web Archive", note="внешний API"),
    Check("block-lists", "Блок-листы", note="медленно, много DNS"),
    Check("linked-pages", "Внутренние/внешние ссылки", note="медленно"),
    Check("subdomains", "Поддомены", note="медленно"),
    Check("tls-labs", "SSL Labs", note="очень медленно"),
    Check("trace-route", "Трассировка", note="нужен traceroute"),
    # --- Нужен браузер (Chromium) ---
    Check("tech-stack", "Технологии (Wappalyzer)", browser=True, note="нужен Chromium"),
    Check("screenshot", "Скриншот", browser=True, note="нужен Chromium"),
    # --- Нужен API-ключ ---
    Check("shodan", "Shodan", needs_key="SHODAN_API_KEY"),
    Check("quality", "Качество (Lighthouse)", needs_key="GOOGLE_CLOUD_API_KEY"),
    Check("threats", "Угрозы (Safe Browsing)", needs_key="GOOGLE_CLOUD_API_KEY"),
)

BY_NAME: dict[str, Check] = {c.name: c for c in CHECKS}

# Все env-переменные ключей, которые пользователь может задать.
KEY_ENV_NAMES: tuple[str, ...] = tuple(
    dict.fromkeys(c.needs_key for c in CHECKS if c.needs_key)
)


def default_enabled() -> list[str]:
    return [c.name for c in CHECKS if c.default_on]


def title_of(name: str) -> str:
    c = BY_NAME.get(name)
    return c.title if c else name
