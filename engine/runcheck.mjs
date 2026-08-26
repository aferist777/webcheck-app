#!/usr/bin/env node
// Тонкий раннер поверх модулей web-check (api/*.js).
//
// Запуск:  node runcheck.mjs <url> <check1,check2,...>
// API-ключи проверок (SHODAN_API_KEY и т.п.) берутся из переменных окружения процесса —
// бот подставляет их per-запуск, поэтому гонок по process.env между пользователями нет.
//
// Для каждой проверки в stdout печатается ОДНА строка NDJSON по мере готовности:
//   {"check":"ssl","status":"ok","ms":812,"data":{...}}
//   {"check":"shodan","status":"skipped","ms":3,"data":{"skipped":"..."}}
//   {"check":"dns","status":"error","ms":40021,"error":"..."}
// Это даёт стрим «после каждой проверки» — Python читает строки и редактирует сообщение домена.

// Обёртка web-check (_common/middleware.js) выбирает Express-режим, когда PLATFORM=NODE.
// Должно быть выставлено ДО импорта любого api-модуля.
if (!process.env.PLATFORM) process.env.PLATFORM = 'NODE';
// Таймаут одной проверки (мс). Можно переопределить из окружения.
if (!process.env.PUBLIC_API_TIMEOUT_LIMIT) process.env.PUBLIC_API_TIMEOUT_LIMIT = '30000';

const CONCURRENCY = parseInt(process.env.RUNCHECK_CONCURRENCY || '4', 10);

const [, , rawUrl, rawChecks] = process.argv;

if (!rawUrl || !rawChecks) {
  process.stderr.write('Usage: node runcheck.mjs <url> <check1,check2,...>\n');
  process.exit(2);
}

const checks = rawChecks
  .split(',')
  .map((c) => c.trim().toLowerCase())
  .filter(Boolean)
  // Защита от path traversal: имена модулей web-check — только [a-z0-9-]
  .filter((c) => /^[a-z0-9-]+$/.test(c));

// Печать одной NDJSON-строки атомарно.
const emit = (obj) => process.stdout.write(JSON.stringify(obj) + '\n');

// Мини мок req/res под vercelHandler(request, response) из middleware.js.
const invoke = (handler, url) =>
  new Promise((resolve) => {
    let settled = false;
    const finish = (body, statusCode) => {
      if (settled) return;
      settled = true;
      resolve({ body, statusCode });
    };
    const res = {
      statusCode: 200,
      status(code) {
        this.statusCode = code;
        return this;
      },
      json(obj) {
        finish(obj, this.statusCode);
        return this;
      },
      send(obj) {
        finish(obj, this.statusCode);
        return this;
      },
      end(obj) {
        finish(obj ?? null, this.statusCode);
        return this;
      },
      setHeader() {
        return this;
      },
    };
    const req = { query: { url }, headers: {}, method: 'GET' };
    Promise.resolve(handler(req, res)).catch((err) =>
      finish({ error: err?.message || String(err) }, 500),
    );
  });

const classify = (body, statusCode) => {
  if (body && typeof body === 'object') {
    if ('error' in body) return 'error';
    if ('skipped' in body) return 'skipped';
  }
  if (statusCode && statusCode >= 400) return 'error';
  return 'ok';
};

async function runOne(name) {
  const startedAt = process.hrtime.bigint();
  const ms = () => Number((process.hrtime.bigint() - startedAt) / 1000000n);
  try {
    const mod = await import(new URL(`./api/${name}.js`, import.meta.url));
    const handler = mod.handler || mod.default;
    if (typeof handler !== 'function') {
      return emit({ check: name, status: 'error', ms: ms(), error: 'no handler export' });
    }
    const { body, statusCode } = await invoke(handler, rawUrl);
    const status = classify(body, statusCode);
    if (status === 'error') {
      emit({ check: name, status, ms: ms(), error: (body && body.error) || `HTTP ${statusCode}` });
    } else {
      emit({ check: name, status, ms: ms(), data: body });
    }
  } catch (err) {
    emit({ check: name, status: 'error', ms: ms(), error: err?.message || String(err) });
  }
}

// Простой пул с ограничением параллельности; строки печатаются по мере готовности.
async function main() {
  const queue = [...checks];
  const workers = Array.from({ length: Math.max(1, CONCURRENCY) }, async () => {
    while (queue.length) {
      const name = queue.shift();
      await runOne(name);
    }
  });
  await Promise.all(workers);
}

main().then(
  () => process.exit(0),
  (err) => {
    process.stderr.write(`runcheck fatal: ${err?.stack || err}\n`);
    process.exit(1);
  },
);
