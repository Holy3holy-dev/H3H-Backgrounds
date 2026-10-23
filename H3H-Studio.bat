@echo off
chcp 65001 >nul
title H3H Background Studio (4IFIR)
echo ===================================================
echo   H3H BACKGROUND STUDIO - 4IFIR EXPRESS EDITION
echo ===================================================
echo [*] Запуск H3H Studio...
py -3 -m studio.h3h_studio.main
if %ERRORLEVEL% NEQ 0 (
    python -m studio.h3h_studio.main
)
