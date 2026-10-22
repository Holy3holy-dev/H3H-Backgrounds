@echo off
title H3H Community Telegram Uploader Bot
cd /d "%~dp0"
set PYTHONUNBUFFERED=1
echo ==============================================================
echo   H3H BACKGROUNDS - COMMUNITY TELEGRAM UPLOADER BOT
echo   Direct Link: https://t.me/h3h_uploader_bot
echo ==============================================================
echo [*] Terminating any stale background bot instances...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name like 'python%' and commandLine like '%%tg_bot/bot.py%%'\" | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo [*] Starting Telegram Bot (@h3h_uploader_bot)...
py -3 -u tg_bot/bot.py
pause
