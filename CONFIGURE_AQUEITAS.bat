@echo off
title Aqueitas Setup Wizard
echo.
echo   ==============================================
echo   AQUEITAS ^| Setup Wizard
echo   ==============================================
echo.
echo   This wizard will ask for your API keys and
echo   write your configuration files automatically.
echo   You only need to do this once.
echo.
python "%~dp0aq.py" configure
echo.
pause
