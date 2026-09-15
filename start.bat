@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  echo [en-learn] First run: creating virtual environment...
  python -m venv backend\.venv
  if errorlevel 1 (
    echo [en-learn] Failed to create venv. Is Python 3.10+ installed and on PATH?
    pause
    exit /b 1
  )
  "backend\.venv\Scripts\python.exe" -m pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo [en-learn] pip install failed. Check your network.
    pause
    exit /b 1
  )
)

echo [en-learn] Starting at http://127.0.0.1:8420 ...
"backend\.venv\Scripts\python.exe" backend\main.py
pause
