@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    .venv\Scripts\python -m pip install -r requirements.txt -q
)

if "%~1"=="" (
    echo.
    echo  Life OS - capture
    echo  Paste URL or file path, then Enter:
    echo.
    set /p SOURCE=
    .venv\Scripts\python capture.py "!SOURCE!"
) else (
    .venv\Scripts\python capture.py %*
)

.venv\Scripts\python generate_vault_pages.py
echo.
pause
