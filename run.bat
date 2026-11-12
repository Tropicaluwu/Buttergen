@echo off

:: start in this file's folder, even when run as administrator or from a shortcut
cd /d "%~dp0"

uv sync --extra discord || ( pause & exit /b )
uv run --extra discord main.py || ( pause & exit /b )