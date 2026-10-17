@echo off
setlocal
cd /d "%~dp0"
title PRIMETONE STEMS

if exist ".venv\installed.flag" goto run

where py >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Trying to install Python 3.11 automatically...
  winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
  echo.
  echo If that succeeded, CLOSE this window and double-click START.bat again.
  echo If it failed, install Python 3.11 from python.org ^(tick "Add python.exe to PATH"^), then run START.bat again.
  pause
  exit /b 1
)

echo First-time setup: downloading components. This can take 10-20 minutes. Please wait...
py -3.11 -m venv .venv
if errorlevel 1 (
  echo Could not create the environment. Python 3.11 is required ^(3.10-3.12 also work^).
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installation failed. Take a screenshot of this window and send it for help.
  pause
  exit /b 1
)
echo ok> ".venv\installed.flag"

:run
".venv\Scripts\python.exe" run.py
if errorlevel 1 pause
