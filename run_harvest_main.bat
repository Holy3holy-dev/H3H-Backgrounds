@echo off
chcp 65001 > nul
title H3H Backgrounds - Main Continuous Harvester (MoeWalls / Live Wallpapers)
echo ========================================================
echo   H3H Backgrounds - Automated Harvester (MAIN STREAM)
echo   Source: MoeWalls (Live Video Wallpapers with Audio)
echo ========================================================
echo.

cd /d "%~dp0"
py -3 scripts\auto_video_harvester.py --mode main --source moewalls --codec h264 --limit 5 --continuous --interval 45
pause
