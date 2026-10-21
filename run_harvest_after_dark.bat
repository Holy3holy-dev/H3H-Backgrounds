@echo off
chcp 65001 > nul
title H3H After Dark - Continuous Harvester
echo ========================================================
echo   H3H Backgrounds - Automated Harvester (AFTER DARK)
echo   Sources: MoeWalls (18+ / Ecchi / Waifus)
echo ========================================================
echo.

cd /d "%~dp0"
py -3 scripts\auto_video_harvester.py --mode after-dark --codec h264 --limit 5 --continuous --interval 45
pause
