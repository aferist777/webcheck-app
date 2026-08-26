"""Форматирование результатов в Telegram MarkdownV2.

Главное: каждое значение, приходящее из проверок, экранируется через esc().
Разметку (* для жирного, _ для курсива) добавляем вокруг уже экранированного текста.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import checks as checks_catalog

# Уровни и эмодзи статуса.
EMOJI = {
    "ok": "✅",
    "warn": "⚠️",
    "error": "❌",
    "skipped": "⏭",
    "pending": "⏳",
}

_MD_SPECIAL = set(r"_*[]()~`>#+-=|{}.!\\")


def esc(text: object) -> str:
    """Экранирование для Telegram MarkdownV2."""
    return "".join("\\" + ch if ch in _MD_SPECIAL else ch for ch in str(text))


def html_escape(text: object) -> str:
    """Экранирование для Telegram HTML / HTML-документа."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _bold(text: object) -> str:
    return f"*{esc(text)}*"


def _italic(text: object) -> str:
    return f"_{esc(text)}_"


def _trunc(text: object, n: int = 70) -> str:
    s = str(text)
    return s if len(s) <= n else s[: n - 1] + "…"


# --- Вспомогательные парсеры дат ---
def _days_until_gmt(gmt_str: str) -> int | None:
    # Формат вида "Aug  2 23:59:59 2026 GMT"
    try:
        parts = gmt_str.split()
        if parts and parts[-1].isalpha():
            parts = parts[:-1]
        dt = datetime.strptime(" ".join(parts), "%b %d %H:%M:%S %Y").replace(
            tzinfo=timezone.utc
        )
        return (dt - datetime.now(timezone.utc)).days
    except (ValueError, TypeError):
        return None


def _days_until_iso(iso_str: str) -> int | None:
    try:
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt - datetime.now(timezone.utc)).days
    except (ValueError, TypeError):
        return None


# --- Суммаризаторы: data(dict) -> (level, short_text) ---
def _s_get_ip(d):
    return "ok", f"{d.get('ip', '?')} (IPv{d.get('family', '?')})"


def _s_dns(d):
    a, aaaa, mx = len(d.get("A") or []), len(d.get("AAAA") or []), len(d.get("MX") or [])
    level = "ok" if (a or aaaa) else "warn"
    return level, f"A:{a} · AAAA:{aaaa} · MX:{mx}"


def _s_ssl(d):
    if d.get("isValid") is False:
        return "warn", "сертификат невалиден"
    days = _days_until_gmt(d.get("valid_to", ""))
    issuer = (d.get("issuer") or {}).get("O") or (d.get("issuer") or {}).get("CN") or "?"
    if days is None:
        return "ok", _trunc(issuer)
    level = "warn" if days < 14 else "ok"
    return level, f"{_trunc(issuer, 32)} · {days} дн."


def _s_tls(d):
    proto = d.get("protocol", "?")
    cipher = (d.get("cipher") or {}).get("name", "")
    weak = proto in {"SSLv3", "TLSv1", "TLSv1.1"} or d.get("forwardSecrecy") is False
    return ("warn" if weak else "ok"), f"{proto} · {_trunc(cipher, 28)}"


def _s_hsts(d):
    if d.get("hstsHeader"):
        return "ok", "preload-ready" if d.get("compatible") else "включён"
    return "warn", "не задан"


def _s_http_security(d):
    keys = [
        "contentSecurityPolicy",
        "strictTransportPolicy",
        "xContentTypeOptions",
        "xFrameOptions",
        "xXSSProtection",
        "referrerPolicy",
        "permissionsPolicy",
        "crossOriginOpenerPolicy",
        "crossOriginResourcePolicy",
        "crossOriginEmbedderPolicy",
    ]
    present = sum(1 for k in keys if d.get(k))
    missing_critical = not d.get("contentSecurityPolicy") or not d.get(
        "strictTransportPolicy"
    )
    return ("warn" if missing_critical else "ok"), f"{present}/{len(keys)} заголовков"


def _s_security_txt(d):
    if d.get("isPresent"):
        n = len(d.get("fields") or {})
        return "ok", f"есть ({n} полей)"
    return "ok", "нет"


def _s_robots(d):
    return "ok", f"{len(d.get('robots') or [])} правил"


def _s_sitemap(d):
    if isinstance(d, dict) and d.get("url"):
        return "ok", "найден"
    return "ok", "найден"


def _s_social(d):
    return "ok", _trunc(d.get("title") or d.get("ogTitle") or "теги найдены", 48)


def _s_headers(d):
    return "ok", f"{len(d)} заголовков"


def _s_redirects(d):
    chain = d.get("redirects") or []
    if len(chain) <= 1:
        return "ok", "без редиректов"
    return "ok", f"{len(chain) - 1} перенаправл. → {_trunc(chain[-1], 36)}"


def _s_txt(d):
    return "ok", f"{len(d)} записей"


def _s_dnssec(d):
    enabled = (d.get("DS") or {}).get("isFound") or (d.get("DNSKEY") or {}).get("isFound")
    return ("ok" if enabled else "warn"), ("включён" if enabled else "выключен")


def _s_dns_server(d):
    return "ok", f"{len(d.get('dns') or [])} серверов"


def _s_firewall(d):
    if d.get("hasWaf"):
        return "ok", f"обнаружен{(' (' + d['waf'] + ')') if d.get('waf') else ''}"
    return "ok", "не обнаружен"


def _s_mail(d):
    mx = len(d.get("mxRecords") or [])
    svc = (d.get("mailServices") or [{}])
    provider = svc[0].get("provider") if svc and isinstance(svc[0], dict) else None
    txt = " ".join(" ".join(t) if isinstance(t, list) else str(t) for t in (d.get("txtRecords") or []))
    dmarc = "DMARC" if "v=DMARC1" in txt else "без DMARC"
    level = "ok" if mx else "warn"
    return level, f"MX:{mx} · {provider or '?'} · {dmarc}"


def _s_status(d):
    up = d.get("isUp")
    code = d.get("responseCode", "?")
    rt = d.get("responseTime")
    rt_s = f"{round(rt)} мс" if isinstance(rt, (int, float)) else ""
    level = "ok" if up and (not isinstance(code, int) or code < 400) else "warn"
    return level, f"{code} · {rt_s}".strip(" ·")


def _s_location(d):
    city = d.get("city") or ""
    cc = d.get("country_code") or d.get("country_name") or ""
    org = _trunc(d.get("org") or "", 28)
    return "ok", ", ".join(x for x in [f"{city} {cc}".strip(), org] if x)


def _s_ports(d):
    op = d.get("openPorts") or []
    return "ok", ("открыто: " + ", ".join(str(p) for p in op)) if op else "нет открытых"


def _s_whois(d):
    reg = d.get("registrar") or "?"
    days = _days_until_iso(d.get("expires", "")) if d.get("expires") else None
    if days is None:
        return "ok", _trunc(reg, 40)
    level = "warn" if days < 30 else "ok"
    return level, f"{_trunc(reg, 28)} · до истеч. {days} дн."


_SUMMARIZERS = {
    "get-ip": _s_get_ip,
    "dns": _s_dns,
    "ssl": _s_ssl,
    "tls-connection": _s_tls,
    "hsts": _s_hsts,
    "http-security": _s_http_security,
    "security-txt": _s_security_txt,
    "robots-txt": _s_robots,
    "sitemap": _s_sitemap,
    "social-tags": _s_social,
    "headers": _s_headers,
    "redirects": _s_redirects,
    "txt-records": _s_txt,
    "dnssec": _s_dnssec,
    "dns-server": _s_dns_server,
    "firewall": _s_firewall,
    "mail-config": _s_mail,
    "status": _s_status,
    "location": _s_location,
    "ports": _s_ports,
    "whois": _s_whois,
}


def summarize(name: str, data) -> tuple[str, str]:
    """Возвращает (level, короткий текст) для успешной проверки."""
    fn = _SUMMARIZERS.get(name)
    if not fn or not isinstance(data, dict):
        # Универсальный фолбэк.
        if isinstance(data, dict):
            return "ok", f"{len(data)} полей"
        return "ok", "готово"
    try:
        return fn(data)
    except Exception:
        return "ok", "готово"


def render_domain(
    domain: str,
    ordered_checks: list[str],
    results: dict[str, dict],
    done: bool,
) -> str:
    """Собирает текст сообщения по домену (MarkdownV2)."""
    lines = [f"🔎 {_bold(domain)}"]
    counts = {"ok": 0, "warn": 0, "error": 0, "skipped": 0}
    for name in ordered_checks:
        title = checks_catalog.title_of(name)
        r = results.get(name)
        if r is None:
            emoji, summary = EMOJI["pending"], "…"
        else:
            level = r["level"]
            counts[level] = counts.get(level, 0) + 1
            emoji = EMOJI.get(level, "•")
            summary = r["text"]
        lines.append(f"{emoji} {esc(title)}: {esc(_trunc(summary))}")

    if done:
        footer = (
            f"{EMOJI['ok']}{counts['ok']}  "
            f"{EMOJI['warn']}{counts['warn']}  "
            f"{EMOJI['error']}{counts['error']}  "
            f"{EMOJI['skipped']}{counts['skipped']}"
        )
        lines.append("")
        lines.append(_italic("Готово") + "  ·  " + esc(footer))
    else:
        progress = len([n for n in ordered_checks if n in results])
        lines.append("")
        lines.append(_italic(f"проверка… {progress}/{len(ordered_checks)}"))
    return "\n".join(lines)


def counts_line(results: dict[str, dict]) -> str:
    c = {"ok": 0, "warn": 0, "error": 0, "skipped": 0}
    for r in results.values():
        lvl = r.get("level")
        if lvl in c:
            c[lvl] += 1
    return (
        f"{EMOJI['ok']}{c['ok']}  {EMOJI['warn']}{c['warn']}  "
        f"{EMOJI['error']}{c['error']}  {EMOJI['skipped']}{c['skipped']}"
    )


def render_domain_html(
    domain: str,
    ordered_checks: list[str],
    results: dict[str, dict],
    done: bool,
) -> str:
    """Компактное сообщение (Telegram HTML): заголовок + сводка + детали в дропдауне."""
    he = html_escape
    counts = {"ok": 0, "warn": 0, "error": 0, "skipped": 0}
    detail = []
    for name in ordered_checks:
        title = checks_catalog.title_of(name)
        r = results.get(name)
        if r is None:
            emoji, summary = EMOJI["pending"], "…"
        else:
            level = r["level"]
            counts[level] = counts.get(level, 0) + 1
            emoji = EMOJI.get(level, "•")
            summary = r["text"]
        detail.append(f"{emoji} {he(title)}: {he(_trunc(summary, 90))}")

    # Ошибка самого процесса (ключ "_"), если есть.
    if "_" in results:
        detail.append(f"{EMOJI['error']} {he(results['_']['text'])}")

    if done:
        head = (
            f"🔎 <b>{he(domain)}</b> — {EMOJI['ok']}{counts['ok']} "
            f"{EMOJI['warn']}{counts['warn']} {EMOJI['error']}{counts['error']} "
            f"{EMOJI['skipped']}{counts['skipped']}"
        )
    else:
        progress = len([n for n in ordered_checks if n in results])
        head = f"🔎 <b>{he(domain)}</b> — <i>проверка… {progress}/{len(ordered_checks)}</i>"

    body = "\n".join(detail)
    return f"{head}\n<blockquote expandable>{body}</blockquote>"


def _counts(results: dict[str, dict], ordered: list[str]) -> dict[str, int]:
    c = {"ok": 0, "warn": 0, "error": 0, "skipped": 0}
    for name in ordered:
        r = results.get(name)
        if r and r.get("level") in c:
            c[r["level"]] += 1
    return c


def _counts_suffix(c: dict[str, int]) -> str:
    return (
        f"{EMOJI['ok']}{c['ok']} {EMOJI['warn']}{c['warn']} "
        f"{EMOJI['error']}{c['error']} {EMOJI['skipped']}{c['skipped']}"
    )


def render_progress_html(domain: str, ordered_checks: list[str], results: dict[str, dict]) -> str:
    """Короткая статус-строка для временного сообщения о ходе проверки (Telegram HTML)."""
    he = html_escape
    done = len([n for n in ordered_checks if n in results])
    c = _counts(results, ordered_checks)
    return f"🔎 <b>{he(domain)}</b> — ⏳ {done}/{len(ordered_checks)}  {_counts_suffix(c)}"


def _detail_lines(domain: str, ordered_checks: list[str], results: dict[str, dict]) -> list[str]:
    he = html_escape
    lines = []
    for name in ordered_checks:
        title = checks_catalog.title_of(name)
        r = results.get(name)
        if r is None:
            emoji, summary = EMOJI["pending"], "…"
        else:
            emoji = EMOJI.get(r["level"], "•")
            summary = r["text"]
        lines.append(f"{emoji} {he(title)}: {he(_trunc(summary, 80))}")
    if "_" in results:
        lines.append(f"{EMOJI['error']} {he(results['_']['text'])}")
    return lines


def render_caption_html(
    domain: str,
    ordered_checks: list[str],
    results: dict[str, dict],
    max_len: int = 1000,
) -> str:
    """Компактный отчёт для подписи к файлу/фото: сводка + детали в дропдауне (с обрезкой)."""
    he = html_escape
    c = _counts(results, ordered_checks)
    head = f"🔎 <b>{he(domain)}</b> — {_counts_suffix(c)}"
    lines = _detail_lines(domain, ordered_checks, results)

    # Бюджет считаем по видимому тексту (HTML-теги в лимит подписи не входят).
    used = len(domain) + 24  # запас под сводку/эмодзи
    body, truncated = [], 0
    for i, line in enumerate(lines):
        if used + len(line) + 1 <= max_len:
            body.append(line)
            used += len(line) + 1
        else:
            truncated = len(lines) - i
            break
    if truncated:
        body.append(f"… ещё {truncated} — в файле")
    return f"{head}\n<blockquote expandable>{chr(10).join(body)}</blockquote>"
