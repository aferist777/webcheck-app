# Запуск Telegram-бота web-check (Windows PowerShell).
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

# 1) Зависимости движка (ставятся один раз).
if (-not (Test-Path "$root\engine\node_modules")) {
    Write-Host "Устанавливаю зависимости движка (npm install)..." -ForegroundColor Cyan
    Push-Location "$root\engine"
    npm install --no-audit --no-fund
    Pop-Location
}

# 2) Python-зависимости.
Write-Host "Устанавливаю Python-зависимости..." -ForegroundColor Cyan
python -m pip install -q -r "$root\requirements.txt"

# 3) Проверка .env.
if (-not (Test-Path "$root\.env")) {
    Write-Host "Нет файла .env. Скопируйте .env.example -> .env и заполните BOT_TOKEN и OWNER_ID." -ForegroundColor Yellow
    exit 1
}

# 4) Запуск бота (long polling).
Write-Host "Запускаю бота..." -ForegroundColor Green
python -m bot
