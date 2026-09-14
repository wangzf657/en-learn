@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [en-learn] 首次运行，正在创建虚拟环境...
  python -m venv .venv
  if errorlevel 1 (
    echo [en-learn] 创建虚拟环境失败，请确认已安装 Python 3.10+
    pause
    exit /b 1
  )
  ".venv\Scripts\pip.exe" install -r backend\requirements.txt
  if errorlevel 1 (
    echo [en-learn] 依赖安装失败，请检查网络
    pause
    exit /b 1
  )
)

echo [en-learn] 启动中，浏览器将自动打开 http://127.0.0.1:8420
".venv\Scripts\python.exe" backend\main.py
pause
