@echo off
title H3H Wallpaper Engine Studio (Drive H:)
cd /d "%~dp0"
echo ==============================================================
echo   H3H WALLPAPER ENGINE STUDIO (DRIVE H: STAGING)
echo ==============================================================
echo [*] Opening visual dashboard in your browser...
start http://localhost:8090
echo [*] Starting local studio server...
py -3 scripts/h3h_wallpaper_studio.py
pause
