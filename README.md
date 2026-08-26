# Web-Check Telegram бот

Личный Telegram-бот для пакетной проверки доменов. Использует движок
[lissy93/web-check](https://github.com/lissy93/web-check) как источник проверок
(DNS, SSL/TLS, security-заголовки, WHOIS, порты и т.д.), а интерфейс, расписание и
отчёты — на Python.

- Вы ведёте список доменов прямо в боте.
- Привязываете опциональные API-ключи (Shodan, Google) командой `/setkey`.
- Настраиваете периодичность (каждые 6 / 12 / 24 ч).
- Получаете результат **Markdown-разметкой в реальном времени**: на каждый домен —
  одно сообщение, которое дополняется после каждой проверки.

## Архитектура

```
Telegram ──► aiogram-бот (Python)
                ├─ SQLite: домены, ключи, проверки, интервал
                ├─ APScheduler: периодический прогон
                └─ runner ─► node engine/runcheck.mjs <домен> <проверки>
                              (модули web-check, ключи через env, NDJSON в stdout)
```

На каждый домен запускается один Node-процесс `engine/runcheck.mjs`, который выполняет
выбранные проверки и печатает по строке NDJSON на каждую готовую проверку. Бот читает
эти строки на лету и редактирует сообщение домена.

## Установка

Требуется **Node.js ≥ 22** и **Python ≥ 3.10**.

```powershell
# 1. Зависимости движка (один раз)
cd engine
npm install --no-audit --no-fund
cd ..

# 2. Python-зависимости
python -m pip install -r requirements.txt

# 3. Настройки
copy .env.example .env
#   затем впишите в .env: BOT_TOKEN и OWNER_ID
```

`.env`:
- `BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather).
- `OWNER_ID` — ваш числовой Telegram id (узнать: [@userinfobot](https://t.me/userinfobot)).

> ⚠️ **Безопасность:** если токен где-то засветился — перевыпустите его в @BotFather
> (`/revoke`). Токен и ключи хранятся только в `.env` / локальной БД (`data/config.db`),
> которые в git не попадают (см. `.gitignore`).

## Запуск

```powershell
.\run.ps1
```

или вручную:

```powershell
python -m bot
```

## Управление

Всё управление — через inline-меню (`/start` или `/menu`). Разделы с пояснениями:
🌐 Домены · 🧪 Проверки · 🔑 API-ключи · ⏱ Периодичность · ▶️ Запустить · 📊 Статус · ❓ Помощь.
Навигация кнопками, ввод доменов и ключей — ответным сообщением (сообщение с ключом удаляется).

Команды-ярлыки:

| Команда | Что делает |
|---|---|
| `/menu`, `/start` | открыть меню |
| `/run` | перейти к запуску проверки |
| `/status` | текущие настройки и время следующего запуска |
| `/add dom1 dom2` | быстро добавить домены |
| `/setkey ENV значение` | задать API-ключ |
| `/help` | как пользоваться |

## Отчёты и скриншоты

Домены проверяются **по очереди** (по одному сайту за раз), поэтому сообщения по разным
сайтам не перемешиваются. По каждому домену:
- во время проверки — временное статус-сообщение с прогрессом (после удаляется);
- **скриншот** главной страницы — фото в чат;
- **HTML-файл** — подробный отчёт; в его подписи идёт компактная сводка (✅/⚠️/❌/⏭) и детали
  по проверкам в раскрывающемся блоке («expandable blockquote»), обрезанные под лимит подписи.
  В самом файле — пояснения по каждой проверке, выделенные значения, «сырые» данные в
  сворачиваемых блоках и встроенный скриншот.

Итого обычно **2 сообщения на сайт** (скриншот + файл с отчётом). Если выключить файл —
отчёт уходит в подписи к скриншоту; если выключить скриншот — остаётся файл (или сообщение).

Скриншоты делаются системным **Chrome или Edge** через `engine/screenshot.mjs`
(пакет `puppeteer-core`, без скачивания Chromium) и снимаются параллельно с проверками.
Если браузер не найден — скриншоты пропускаются. В меню есть раздел **📄 Отчёт** с
переключателями «HTML-отчёт» и «Скриншот».

## Проверки

По умолчанию включён набор без внешних ключей и браузера: `dns`, `ssl`,
`tls-connection`, `http-security`, `headers`, `hsts`, `security-txt`, `redirects`,
`robots-txt`, `sitemap`, `whois`, `dnssec`, `social-tags`, `status`, `mail-config`,
`txt-records`, `ports`, `dns-server`, `firewall`, `location`, `get-ip`.

Доступны, но выключены по умолчанию:
- **Нужен ключ:** `shodan` (`SHODAN_API_KEY`), `quality` / `threats` (`GOOGLE_CLOUD_API_KEY`).
- **Нужен браузер (Chromium):** `cookies`, `tech-stack`, `screenshot`.
- **Медленные / внешние:** `tls-labs`, `subdomains`, `block-lists`, `carbon`, `rank`,
  `archives`, `linked-pages`, `trace-route` (нужен системный `traceroute`).

### Включить браузерные проверки

Они требуют дополнительных npm-пакетов и Chromium:

```powershell
cd engine
npm install puppeteer wappalyzer puppeteer-core "@sparticuz/chromium" --no-audit --no-fund
```

## Структура

```
engine/                 модули web-check (vendored) + runcheck.mjs
  package.json          лёгкий манифест (только backend-зависимости)
  package.web-check.json  оригинальный манифест web-check (справочно)
bot/
  config.py  db.py  access.py  checks.py
  formatting.py  runner.py  scheduler.py
  handlers/  settings.py  run.py
requirements.txt  run.ps1  .env.example
```

Движок основан на [web-check](https://github.com/lissy93/web-check) (лицензия MIT, © Alicia Sykes).
