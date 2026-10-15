@echo off
chcp 65001 >nul
title Nova Windows Tools

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "nova_windows_tools.py"
) else (
    python "nova_windows_tools.py"
)
pause
