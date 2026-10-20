@echo off
title H3H-Backgrounds: SteamGridDB Auto-Harvester
cd /d "%~dp0"
set PYTHONUNBUFFERED=1

:: Redirect temp directory to drive H: to protect drive C: from running out of space
if not exist "H:\H3H_Backgrounds\temp" mkdir "H:\H3H_Backgrounds\temp"
set TEMP=H:\H3H_Backgrounds\temp
set TMP=H:\H3H_Backgrounds\temp

py scripts\auto_harvest_menu.py
if errorlevel 1 (
    echo.
    echo [ERROR] Python script exited with an error.
    pause
)
