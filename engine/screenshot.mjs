#!/usr/bin/env node
// Снимок страницы системным Chrome/Edge через puppeteer-core (без скачивания Chromium).
// Запуск: node screenshot.mjs <url> <outPath> <browserExePath>
// Печатает "OK <bytes>" в stdout при успехе, иначе пишет ошибку в stderr и выходит с кодом 1.
import puppeteer from 'puppeteer-core';
import { promises as fs } from 'fs';

const [, , url, outPath, exe] = process.argv;
if (!url || !outPath || !exe) {
  process.stderr.write('Usage: node screenshot.mjs <url> <outPath> <browserExe>\n');
  process.exit(2);
}

let browser = null;
try {
  browser = await puppeteer.launch({
    executablePath: exe,
    headless: true,
    acceptInsecureCerts: true,
    args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  page.setDefaultNavigationTimeout(20000);
  try {
    await page.goto(url, { waitUntil: 'networkidle2' });
  } catch {
    // частичная загрузка — всё равно пробуем снять то, что есть
  }
  await page.screenshot({ path: outPath, fullPage: false });
  const { size } = await fs.stat(outPath);
  process.stdout.write(`OK ${size}\n`);
} catch (err) {
  process.stderr.write(`screenshot error: ${err?.message || err}\n`);
  process.exit(1);
} finally {
  if (browser) await browser.close().catch(() => {});
}
