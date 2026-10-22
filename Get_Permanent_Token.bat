@echo off
title H3H - Get Permanent Google Drive Token
cd /d "%~dp0"
echo ==============================================================
echo   H3H BACKGROUNDS - GET PERMANENT GOOGLE DRIVE TOKEN
echo ==============================================================
echo [*] Starting token generator...
echo [*] In a moment, Google login will open in your browser.
echo [*] Sign in with marat666musin@gmail.com and click "Allow".
echo ==============================================================
py -3 scripts/get_permanent_token.py
echo.
pause
