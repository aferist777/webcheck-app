"""Сборка самодостаточного HTML-отчёта по домену (с пояснениями и скриншотом)."""
from __future__ import annotations

import base64
import json

from . import checks as checks_catalog
from . import formatting as fmt

he = fmt.html_escape

# Пояснения по каждой проверке (что это и зачем).
EXPLANATIONS: dict[str, str] = {
    "dns": "DNS-записи домена: A/AAAA (IP-адреса), MX (почтовые серверы), NS, TXT, CNAME, SOA.",
    "get-ip": "IP-адрес, на который резолвится домен.",
    "ssl": "SSL/TLS-сертификат: кем выдан, срок действия, валидность цепочки.",
    "tls-connection": "Параметры TLS-соединения: версия протокола, шифр, forward secrecy, ALPN.",
    "http-security": "Наличие ключевых HTTP security-заголовков (CSP, HSTS, X-Frame-Options, X-Content-Type-Options и др.).",
    "headers": "Полный набор HTTP-заголовков ответа сервера.",
    "hsts": "HTTP Strict Transport Security — принудительный HTTPS и готовность к preload-списку браузеров.",
    "security-txt": "Файл /.well-known/security.txt с контактами для сообщений об уязвимостях.",
    "redirects": "Цепочка перенаправлений при заходе на сайт (http→https, www и т.п.).",
    "robots-txt": "Файл robots.txt — правила обхода для поисковых роботов.",
    "sitemap": "Карта сайта (sitemap.xml) для поисковых систем.",
    "whois": "Регистрационные данные домена: регистратор, даты создания и окончания, статусы.",
    "dnssec": "DNSSEC — криптографическая подпись DNS-записей (защита от подмены).",
    "social-tags": "Open Graph и Twitter-теги, отвечающие за превью при шеринге в соцсетях.",
    "cookies": "Cookies, устанавливаемые сайтом при загрузке.",
    "status": "Доступность сайта: код HTTP-ответа и время отклика.",
    "mail-config": "Почтовая конфигурация домена: MX, SPF, DMARC, DKIM, провайдер почты.",
    "txt-records": "TXT-записи DNS: верификации сервисов, SPF, политики.",
    "ports": "Открытые сетевые порты сервера (из типового списка).",
    "dns-server": "Авторитативные DNS-серверы, обслуживающие домен.",
    "firewall": "Признаки WAF/файрвола (web application firewall) перед сайтом.",
    "location": "Геолокация сервера по IP: страна, город, организация, провайдер.",
    "carbon": "Оценка углеродного следа от загрузки страницы.",
    "rank": "Позиция сайта в рейтинге популярности (Tranco).",
    "archives": "Наличие копий сайта в веб-архиве (Wayback Machine).",
    "block-lists": "Проверка домена по публичным блок-листам (спам/угрозы).",
    "linked-pages": "Внутренние и внешние ссылки, найденные на странице.",
    "subdomains": "Обнаруженные поддомены.",
    "tls-labs": "Глубокий аудит TLS-конфигурации (SSL Labs).",
    "trace-route": "Маршрут сетевых пакетов до сервера (traceroute).",
    "tech-stack": "Технологии и фреймворки сайта (Wappalyzer).",
    "screenshot": "Снимок главной страницы.",
    "shodan": "Данные Shodan по хосту (открытые сервисы, баннеры).",
    "quality": "Аудит качества страницы (Lighthouse): производительность, доступность, SEO.",
    "threats": "Проверка на угрозы (Google Safe Browsing).",
}

_LEVEL_RU = {"ok": "OK", "warn": "Предупреждение", "error": "Ошибка", "skipped": "Пропущено"}

_CSS = """
:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#0f1115;color:#e7e9ee}
.wrap{max-width:880px;margin:0 auto;padding:24px 18px 60px}
h1{font-size:22px;margin:0 0 4px;word-break:break-all}
.meta{color:#9aa3b2;font-size:13px;margin-bottom:16px}
.summary{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 22px}
.pill{padding:4px 10px;border-radius:999px;font-size:13px;font-weight:600}
.ok{background:#10391f;color:#7ee2a8}.warn{background:#3d3410;color:#f3d262}
.error{background:#3f1717;color:#f3a0a0}.skipped{background:#262a33;color:#aab2c2}
.shot{margin:0 0 24px;border:1px solid #2a2f3a;border-radius:10px;overflow:hidden}
.shot img{display:block;width:100%;height:auto}
.card{border:1px solid #232834;border-radius:10px;padding:14px 16px;margin:0 0 12px;background:#161a22}
.card h3{margin:0;font-size:16px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.d-ok{background:#3ddc84}.d-warn{background:#f3d262}.d-error{background:#f06565}.d-skipped{background:#7c8597}
.tag{font-size:11px;color:#8b93a3;font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.expl{color:#9aa3b2;font-size:13px;margin:6px 0 8px}
.val{font-size:14px;margin:4px 0}
details{margin-top:8px}
summary{cursor:pointer;color:#8ab4ff;font-size:13px}
pre{white-space:pre-wrap;word-break:break-word;background:#0c0f14;border:1px solid #232834;border-radius:8px;padding:10px;font:12px/1.45 Consolas,monospace;color:#cdd3df;overflow:auto;max-height:340px}
footer{color:#6b7280;font-size:12px;margin-top:28px;text-align:center}
"""


def _raw_block(r: dict) -> str:
    status = r.get("status")
    if status == "error":
        payload = {"error": r.get("error")}
    elif status == "skipped":
        payload = r.get("data") or {"skipped": r.get("text")}
    else:
        payload = r.get("data")
    if payload in (None, {}, []):
        return ""
    try:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        text = str(payload)
    return f"<details><summary>Данные</summary><pre>{he(text)}</pre></details>"


def build_html(
    domain: str,
    ordered_checks: list[str],
    results: dict[str, dict],
    screenshot_png: bytes | None,
    generated_at: str,
) -> str:
    counts = {"ok": 0, "warn": 0, "error": 0, "skipped": 0}
    for name in ordered_checks:
        r = results.get(name)
        if r and r.get("level") in counts:
            counts[r["level"]] += 1

    parts = [
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>Отчёт — {he(domain)}</title><style>{_CSS}</style></head><body><div class='wrap'>",
        f"<h1>🔎 {he(domain)}</h1>",
        f"<div class='meta'>Отчёт сформирован: {he(generated_at)} · движок web-check</div>",
        "<div class='summary'>"
        f"<span class='pill ok'>OK: {counts['ok']}</span>"
        f"<span class='pill warn'>Предупреждения: {counts['warn']}</span>"
        f"<span class='pill error'>Ошибки: {counts['error']}</span>"
        f"<span class='pill skipped'>Пропущено: {counts['skipped']}</span>"
        "</div>",
    ]

    if screenshot_png:
        b64 = base64.b64encode(screenshot_png).decode("ascii")
        parts.append(f"<div class='shot'><img alt='screenshot' src='data:image/png;base64,{b64}'></div>")

    for name in ordered_checks:
        r = results.get(name) or {"level": "error", "text": "нет ответа", "status": "error", "error": "нет ответа"}
        level = r.get("level", "error")
        title = checks_catalog.title_of(name)
        expl = EXPLANATIONS.get(name, "")
        parts.append(
            "<div class='card'>"
            f"<h3><span class='dot d-{level}'></span>{he(title)} "
            f"<span class='tag'>{he(name)} · {he(_LEVEL_RU.get(level, level))}</span></h3>"
            + (f"<div class='expl'>{he(expl)}</div>" if expl else "")
            + f"<div class='val'>{he(r.get('text', ''))}</div>"
            + _raw_block(r)
            + "</div>"
        )

    if "_" in results:
        parts.append(
            f"<div class='card'><h3><span class='dot d-error'></span>Процесс "
            f"<span class='tag'>error</span></h3><div class='val'>{he(results['_'].get('text',''))}</div></div>"
        )

    parts.append("<footer>Сгенерировано Web-Check ботом</footer></div></body></html>")
    return "".join(parts)
