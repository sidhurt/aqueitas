@echo off
title Aqueitas Installer
echo.
echo   ==============================================
echo   AQUEITAS ^| Installer
echo   ==============================================
echo.
echo   This installs dependencies and configures
echo   the Git commit sensor. Run once after the
echo   Setup Wizard (CONFIGURE_AQUEITAS.bat).
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
