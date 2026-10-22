@echo off
title H3H Community Telegram Uploader Bot
cd /d "%~dp0"
echo ==============================================================
echo   H3H BACKGROUNDS - COMMUNITY TELEGRAM UPLOADER BOT
echo ==============================================================
echo [*] Starting Telegram Bot (@h3h_uploader_bot)...
py -3 tg_bot/bot.py
pause
