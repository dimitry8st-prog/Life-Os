@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Life OS Dashboard

where python >nul 2>nul
if errorlevel 1 (
  echo Python не найден.
  echo Установите Python 3.12 с сайта https://www.python.org/downloads/
  echo При установке включите пункт "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Создаю рабочее окружение...
  python -m venv .venv
  if errorlevel 1 goto :error
)

echo [2/3] Проверяю зависимости...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [3/3] Запускаю Life OS...
echo Браузер откроется автоматически. Для остановки закройте это окно.
".venv\Scripts\python.exe" -m streamlit run dashboard.py
exit /b 0

:error
echo.
echo Не удалось запустить Life OS. Скопируйте текст ошибки из этого окна.
pause
exit /b 1
