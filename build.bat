@echo off
REM One-click release build: frontend build + PyInstaller -> release\EnLearn.exe (single file)
REM Runs on the dev machine (needs Python 3.10+ and Node.js).
REM Output: copy release\EnLearn.exe to any Windows 10+ machine and run it; data is created next to the exe.
REM ASCII only: cmd mangles non-ASCII inside bat files (see AGENTS.md).
setlocal
cd /d "%~dp0"
set "PY=backend\.venv\Scripts\python.exe"
set "PYI=backend\.venv\Scripts\pyinstaller.exe"

if exist "%PY%" goto :venv_ok
echo [build] First run: creating venv and installing deps ...
python -m venv backend\.venv
if errorlevel 1 goto :fail
:venv_ok
"%PY%" -m pip install -r backend\requirements.txt
if errorlevel 1 goto :fail

if exist "frontend\node_modules" goto :fe_deps_ok
echo [build] Installing frontend deps ...
pushd frontend
call npm install
if errorlevel 1 (popd & goto :fail)
popd
:fe_deps_ok

echo [build] Building frontend ...
pushd frontend
call npm run build
if errorlevel 1 (popd & goto :fail)
popd
if exist "frontend\dist\index.html" goto :dist_ok
echo [build] FAILED: frontend\dist\index.html missing
goto :fail
:dist_ok

echo [build] Generating exe icon from mascot.jpg ...
if not exist "%CD%\release\_work" mkdir "%CD%\release\_work"
"%PY%" -c "from PIL import Image; Image.open('frontend/src/assets/mascot.jpg').convert('RGB').save(r'release\_work\EnLearn.ico', format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"
if errorlevel 1 goto :fail

echo [build] Packaging with PyInstaller ...
"%PYI%" --noconfirm --clean --name EnLearn --onefile --icon "%CD%\release\_work\EnLearn.ico" --add-data "%CD%\frontend\dist;frontend\dist" --distpath "%CD%\release" --workpath "%CD%\release\_work" --specpath "%CD%\release" backend\main.py
if errorlevel 1 goto :fail

echo [build] Removing intermediates ...
if exist "%CD%\release\_work" rmdir /s /q "%CD%\release\_work"
if exist "%CD%\release\EnLearn.spec" del /q "%CD%\release\EnLearn.spec"

echo.
echo [build] DONE: release\EnLearn.exe (single file)
echo [build] Copy it to any Windows 10+ machine and run. First run creates a data folder next to the exe.
pause
exit /b 0

:fail
echo.
echo [build] FAILED
pause
exit /b 1
